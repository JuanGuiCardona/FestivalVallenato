"""Reglas de negocio del voto (CU-04 · RF-08 · RN-04 a RN-07 · RNF-05).

Todas las pantallas usan estas funciones, así cada regla vive en un solo lugar.
"""
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from audit.services import registrar
from catalog.models import Categoria, Edicion

from .models import Opcion, Votacion, Voto


class ReglaVoto(Exception):
    """Un voto que no se puede registrar. `codigo` indica a qué pantalla volver."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


# ------------------------------------------------------------------ estados por fechas
def sincronizar_estados(request=None):
    """Abre y cierra las votaciones cuyas fechas ya llegaron (RN-04, CU-07 pasos 5-6)."""
    ahora = timezone.now()
    pendientes = Votacion.objects.filter(
        Q(estado=Votacion.PROXIMA, fecha_apertura__lte=ahora) | Q(estado=Votacion.ABIERTA, fecha_cierre__lte=ahora)
    )
    for votacion in pendientes:
        sincronizar_votacion(votacion)


def sincronizar_votacion(votacion):
    """Igual que la anterior, para una sola votación. Deja la acción en la auditoría."""
    accion = votacion.sincronizar_estado()
    if accion:
        # El sistema actúa solo: la auditoría queda sin usuario («sistema»).
        registrar(None, accion)
    return accion


# ------------------------------------------------------------------ consultas públicas
def votaciones_publicas():
    """Votaciones que ve el público: edición vigente, categoría activa y no en borrador (CU-03)."""
    edicion = Edicion.vigente()
    if edicion is None:
        return Votacion.objects.none()
    return (Votacion.objects
            .filter(categoria__edicion=edicion, categoria__estado=Categoria.ACTIVA)
            .exclude(estado=Votacion.BORRADOR)
            .select_related("categoria"))


def votos_usados(usuario, votacion):
    if not usuario.is_authenticated:
        return 0
    return Voto.objects.filter(usuario=usuario, votacion=votacion, periodo=votacion.periodo_actual(),
                               estado=Voto.REGISTRADO).count()


def alcanzo_limite(usuario, votacion):
    """RN-06: ¿ya usó todos los votos permitidos en el periodo actual?"""
    return usuario.is_authenticated and votos_usados(usuario, votacion) >= votacion.max_votos_por_votante


def ids_con_limite_alcanzado(usuario, votaciones):
    """Para marcar «Ya votaste» en los listados sin hacer una consulta por tarjeta."""
    if not usuario.is_authenticated:
        return set()
    votaciones = list(votaciones)
    if not votaciones:
        return set()
    conteo = {}
    for votacion_id, periodo in (Voto.objects
                                 .filter(usuario=usuario, votacion__in=votaciones, estado=Voto.REGISTRADO)
                                 .values_list("votacion_id", "periodo")):
        conteo[(votacion_id, periodo)] = conteo.get((votacion_id, periodo), 0) + 1
    return {v.pk for v in votaciones if conteo.get((v.pk, v.periodo_actual()), 0) >= v.max_votos_por_votante}


# ------------------------------------------------------------------ emitir voto
def _limite_de_solicitudes(usuario):
    """RNF-04 (preliminar*): frena solicitudes repetitivas de un mismo votante."""
    llave = f"votos-min:{usuario.pk}"
    cuenta = cache.get(llave, 0) + 1
    cache.set(llave, cuenta, 60)
    return cuenta > settings.VOTOS_MAX_POR_MINUTO


def emitir_voto(request, votacion_id, opcion_id):
    """CU-04 pasos 7 y 8: valida las reglas y registra el voto en una transacción atómica.

    Si algo falla, no se guarda nada parcial (8a). Si llegan dos solicitudes
    simultáneas, la restricción única de MySQL deja pasar solo una (7b).
    """
    usuario = request.user
    if not usuario.is_authenticated:
        raise ReglaVoto("sin_sesion", "Tu sesión terminó. Inicia sesión para votar.")
    if usuario.es_administrador:
        raise ReglaVoto("rol", "Las cuentas de administrador no votan. Usa una cuenta de votante*.")
    if _limite_de_solicitudes(usuario):
        raise ReglaVoto("frecuencia", "Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo.")

    with transaction.atomic():
        try:
            votacion = Votacion.objects.select_related("categoria__edicion").get(pk=votacion_id)
        except (Votacion.DoesNotExist, ValueError, TypeError):
            raise ReglaVoto("no_existe", "La votación no existe.")
        sincronizar_votacion(votacion)
        visible = votacion.categoria.activa and votacion.categoria.edicion.estado == Edicion.ACTIVA
        if not votacion.recibe_votos or not visible:
            raise ReglaVoto("no_abierta", "La votación cerró antes de confirmar tu voto.")
        try:
            opcion = votacion.opciones.get(pk=opcion_id, estado=Opcion.ACTIVA)
        except (Opcion.DoesNotExist, ValueError, TypeError):
            raise ReglaVoto("opcion", "Selecciona una opción para continuar.")

        periodo = votacion.periodo_actual()
        usados = Voto.objects.filter(usuario=usuario, votacion=votacion, periodo=periodo).count()
        if usados >= votacion.max_votos_por_votante:
            raise ReglaVoto("ya_voto", "Ya votaste en esta votación.")
        try:
            with transaction.atomic():
                voto = Voto.objects.create(usuario=usuario, votacion=votacion, opcion=opcion,
                                           periodo=periodo, numero=usados + 1)
        except IntegrityError:
            # Otra solicitud del mismo votante ganó la carrera (CU-04 7b).
            raise ReglaVoto("ya_voto", "Ya votaste en esta votación.")

        # RN-13 con secreto del voto: se audita que votó, nunca por cuál opción.
        registrar(request, "Voto registrado", detalle=f"Votación «{votacion.titulo}» · comprobante {voto.codigo}")
    return voto
