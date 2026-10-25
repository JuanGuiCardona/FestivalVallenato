"""Pantallas de votación.

Públicas (CU-03, CU-04): P-05 Votaciones, P-06 Detalle, P-07 Opciones,
P-08 Confirmación y P-09 Comprobante / Ya votaste.
Administración (CU-07, CU-08): A-03 Votaciones y A-04 Opciones.
"""
from django.contrib import messages
from django.db.models import Count, Max
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import ir_a_login, solo_administrador
from audit.services import registrar
from catalog.forms import primer_error
from catalog.models import Categoria, Edicion
from catalog.utils import entero, mover_en_orden

from . import services
from .forms import OpcionForm, VotacionConfigForm, VotacionNuevaForm
from .models import Opcion, Votacion, Voto

AVISO_VOTAR = "Inicia sesión o regístrate para votar. Al entrar volverás a la votación."


# ====================================================================== utilidades
def _votacion_publica(request, pk):
    """La votación que puede ver el público (o cualquiera, si es administrador)."""
    votacion = get_object_or_404(Votacion.objects.select_related("categoria__edicion"), pk=pk)
    if request.user.is_authenticated and request.user.es_administrador:
        return votacion
    visible = (votacion.estado != Votacion.BORRADOR and votacion.categoria.activa
               and votacion.categoria.edicion.estado == Edicion.ACTIVA)
    if not visible:
        raise Http404("Votación no disponible")
    return votacion


def _clave_seleccion(votacion):
    return f"seleccion_{votacion.pk}"


# ====================================================================== públicas
def por_categoria(request, pk):
    """P-05 · CU-03 pasos 3-4 · RF-05: votaciones de la categoría con estado y fechas."""
    services.sincronizar_estados(request)
    categoria = get_object_or_404(Categoria, pk=pk, estado=Categoria.ACTIVA, edicion__estado=Edicion.ACTIVA)
    votaciones = list(services.votaciones_publicas().filter(categoria=categoria))
    return render(request, "voting/p05_votaciones.html", {
        "titulo": "Votaciones disponibles",
        "subtitulo": categoria.nombre,
        "votaciones": votaciones,
        "ya_votadas": services.ids_con_limite_alcanzado(request.user, votaciones),
        "vacio": "Esta categoría aún no tiene votaciones.",
        "volver": reverse("catalog:categorias"),
        "tab": "Categorías",
    })


def detalle(request, pk):
    """P-06 · CU-03 paso 6 · RF-06: descripción, fechas y reglas antes de votar (12.1)."""
    services.sincronizar_estados(request)
    votacion = _votacion_publica(request, pk)
    limite = services.alcanzo_limite(request.user, votacion)
    if votacion.estado == Votacion.PROXIMA:
        pista = "Esta votación aún no abre."
    elif votacion.estado == Votacion.CERRADA:
        pista = "Esta votación ya cerró."
    elif limite:
        pista = ("Ya usaste tu voto de hoy. Podrás volver a votar mañana*."
                 if votacion.periodicidad_voto == Votacion.DIARIA else "Ya votaste en esta votación.")
    else:
        pista = ""
    return render(request, "voting/p06_detalle.html", {
        "v": votacion,
        "puede_votar": votacion.recibe_votos and not limite,
        "pista": pista,
        "opciones": votacion.opciones_activas(),
    })


def opciones(request, pk):
    """P-07 · CU-04 pasos 1-4 · RF-06, RF-07."""
    votacion = _votacion_publica(request, pk)
    services.sincronizar_votacion(votacion)
    if not votacion.recibe_votos:
        # CU-04 2b: votación cerrada o aún no abierta.
        messages.warning(request, "Esta votación no está abierta." if votacion.estado != Votacion.PROXIMA
                         else "Esta votación aún no abre.")
        return redirect("voting:detalle", pk)
    if not request.user.is_authenticated:
        # CU-04 2a: sin sesión pasa por P-03 y regresa (RN-05).
        return ir_a_login(request, AVISO_VOTAR, reverse("voting:opciones", args=[pk]))
    if request.user.es_administrador:
        messages.error(request, "Las cuentas de administrador no votan. Usa una cuenta de votante*.")
        return redirect("voting:detalle", pk)
    if services.alcanzo_limite(request.user, votacion):
        return redirect("voting:ya_voto", pk)

    activas = votacion.opciones_activas()
    seleccion = request.session.get(_clave_seleccion(votacion))
    error = False
    if request.method == "POST":
        elegida = activas.filter(pk=entero(request.POST.get("opcion")) or 0).first()
        if elegida is None:
            error = True  # CU-04 4a: no elige opción.
        else:
            request.session[_clave_seleccion(votacion)] = elegida.pk
            return redirect("voting:confirmar", pk)
    return render(request, "voting/p07_opciones.html", {
        "v": votacion, "opciones": activas, "seleccion": seleccion, "error": error,
    })


def confirmar(request, pk):
    """P-08 · CU-04 pasos 5-9 · RF-07, RF-08: resumen, confirmación explícita y registro."""
    votacion = _votacion_publica(request, pk)
    if not request.user.is_authenticated:
        return ir_a_login(request, "Tu sesión terminó. Inicia sesión para votar.", reverse("voting:opciones", args=[pk]))
    opcion = votacion.opciones_activas().filter(pk=request.session.get(_clave_seleccion(votacion)) or 0).first()
    if opcion is None:
        return redirect("voting:opciones", pk)

    if request.method == "POST":
        try:
            voto = services.emitir_voto(request, votacion.pk, opcion.pk)
        except services.ReglaVoto as regla:
            if regla.codigo == "sin_sesion":
                return ir_a_login(request, regla.mensaje, reverse("voting:opciones", args=[pk]))
            if regla.codigo == "ya_voto":
                return redirect("voting:ya_voto", pk)
            messages.error(request, regla.mensaje)
            if regla.codigo == "opcion":
                return redirect("voting:opciones", pk)
            if regla.codigo == "frecuencia":
                return redirect("voting:confirmar", pk)
            return redirect("voting:detalle", pk)
        request.session.pop(_clave_seleccion(votacion), None)
        return redirect("voting:comprobante", voto.codigo)

    return render(request, "voting/p08_confirmar.html", {"v": votacion, "opcion": opcion})


def comprobante(request, codigo):
    """P-09 · RF-09: confirmación y código de comprobante (solo lo ve quien votó)."""
    if not request.user.is_authenticated:
        raise Http404
    voto = get_object_or_404(Voto.objects.select_related("votacion"), codigo=codigo, usuario=request.user)
    return render(request, "voting/p09_comprobante.html", {"voto": voto, "v": voto.votacion})


def ya_voto(request, pk):
    """P-09 · CU-04 7a: ya votó o alcanzó el límite; no se registra nada."""
    votacion = _votacion_publica(request, pk)
    return render(request, "voting/p09_ya_voto.html", {"v": votacion})


# ====================================================================== administración
def _url_a03(**params):
    url = reverse("voting:admin_votaciones")
    params = {k: v for k, v in params.items() if v}
    return url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")


@solo_administrador
def admin_votaciones(request):
    """A-03 · CU-07 · RF-13: listado con filtro por categoría o estado, alta y configuración."""
    services.sincronizar_estados(request)
    form_nueva = VotacionNuevaForm(request.POST or None)
    if request.method == "POST":
        if form_nueva.is_valid():
            votacion = form_nueva.save(commit=False)
            votacion.descripcion = "Votación en preparación."
            votacion.save()
            registrar(request, f"Votación «{votacion.titulo}» creada en borrador")
            messages.success(request, "Votación creada en borrador.")
            return redirect(_url_a03(categoria=request.GET.get("categoria"), editar=votacion.pk))
        messages.error(request, primer_error(form_nueva))

    filtro_cat = str(entero(request.GET.get("categoria")) or "")
    filtro_estado = request.GET.get("estado", "") if request.GET.get("estado") in dict(Votacion.ESTADOS) else ""
    votaciones = Votacion.objects.select_related("categoria__edicion").annotate(total_votos=Count("votos"))
    if filtro_cat:
        votaciones = votaciones.filter(categoria_id=filtro_cat)
    if filtro_estado:
        votaciones = votaciones.filter(estado=filtro_estado)

    editar = str(entero(request.GET.get("editar")) or "")
    form_config = None
    if editar:
        en_edicion = Votacion.objects.filter(pk=int(editar)).first()
        if en_edicion:
            form_config = VotacionConfigForm(instance=en_edicion)
    return render(request, "voting/a03_votaciones.html", {
        "votaciones": votaciones,
        "categorias": Categoria.objects.select_related("edicion"),
        "estados": Votacion.ESTADOS,
        "filtro_cat": filtro_cat,
        "filtro_estado": filtro_estado,
        "editar": editar,
        "form_config": form_config,
        "ahora": timezone.now(),
    })


@solo_administrador
@require_POST
def admin_votacion_configurar(request, pk):
    votacion = get_object_or_404(Votacion, pk=pk)
    form = VotacionConfigForm(request.POST, instance=votacion)
    volver = _url_a03(categoria=request.POST.get("filtro_categoria"), estado=request.POST.get("filtro_estado"))
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a03(categoria=request.POST.get("filtro_categoria"),
                                 estado=request.POST.get("filtro_estado"), editar=pk))
    cambios = ", ".join(form.fields[c].label or c for c in form.changed_data)
    form.save()
    registrar(request, f"Votación «{votacion.titulo}» configurada", detalle=f"Campos: {cambios}" if cambios else "")
    messages.success(request, "Cambio guardado.")
    services.sincronizar_votacion(votacion)
    return redirect(volver)


@solo_administrador
@require_POST
def admin_votacion_estado(request, pk):
    """Abrir, programar, volver a borrador, cerrar o reabrir (CU-07 pasos 5-6 · RN-09)."""
    votacion = get_object_or_404(Votacion.objects.select_related("categoria__edicion"), pk=pk)
    accion = request.POST.get("accion")
    volver = _url_a03(categoria=request.POST.get("filtro_categoria"), estado=request.POST.get("filtro_estado"))
    ahora = timezone.now()

    def error(texto, nivel=messages.ERROR):
        messages.add_message(request, nivel, texto)
        return redirect(volver)

    if accion == "cerrar" and votacion.estado == Votacion.ABIERTA:
        votacion.estado = Votacion.CERRADA
        votacion.fecha_cierre = ahora
        votacion.save(update_fields=["estado", "fecha_cierre"])
        registrar(request, f"Cierre de «{votacion.titulo}»")
        messages.success(request, "Votación cerrada.")
        return redirect(volver)

    if accion == "reabrir":
        # CU-07 6a: pendiente de validación con el cliente.
        return error("Reabrir una votación cerrada está pendiente de validación con el cliente*.", messages.WARNING)

    if accion == "borrador" and votacion.estado == Votacion.PROXIMA:
        votacion.estado = Votacion.BORRADOR
        votacion.save(update_fields=["estado"])
        registrar(request, f"Programación de «{votacion.titulo}» cancelada")
        messages.success(request, "La votación volvió a borrador.")
        return redirect(volver)

    if accion in ("abrir", "programar") and votacion.estado in (Votacion.BORRADOR, Votacion.PROXIMA):
        if votacion.opciones_activas().count() < 2:
            return error("Una votación necesita al menos 2 opciones activas para abrirse (RN-09).")
        if not votacion.categoria.activa or votacion.categoria.edicion.estado != Edicion.ACTIVA:
            return error("La categoría debe estar activa y pertenecer a la edición vigente.")
        if votacion.fecha_cierre and votacion.fecha_cierre <= ahora:
            return error("La fecha de cierre ya pasó. Configura una nueva antes de abrir.")
        if accion == "programar":
            if not votacion.fecha_apertura or votacion.fecha_apertura <= ahora:
                return error("Para programarla, configura una fecha de apertura futura.")
            votacion.estado = Votacion.PROXIMA
            votacion.save(update_fields=["estado"])
            registrar(request, f"Apertura de «{votacion.titulo}» programada",
                      detalle=f"Abre el {timezone.localtime(votacion.fecha_apertura):%Y-%m-%d %H:%M}")
            messages.success(request, "Votación programada. Se abrirá sola en la fecha indicada.")
            return redirect(volver)
        votacion.estado = Votacion.ABIERTA
        votacion.fecha_apertura = ahora
        votacion.save(update_fields=["estado", "fecha_apertura"])
        registrar(request, f"Apertura de «{votacion.titulo}»")
        messages.success(request, "Votación abierta.")
        return redirect(volver)

    return error("Esa acción no aplica al estado actual de la votación.")


# ---------------------------------------------------------------- opciones (CU-08)
def _url_a04(votacion_id, **extra):
    url = reverse("voting:admin_opciones") + f"?votacion={votacion_id}"
    for k, v in extra.items():
        url += f"&{k}={v}"
    return url


@solo_administrador
def admin_opciones(request):
    """A-04 · CU-08 · RF-14: opciones de una votación."""
    votaciones = Votacion.objects.select_related("categoria")
    votacion = votaciones.filter(pk=entero(request.GET.get("votacion")) or 0).first() or votaciones.first()
    lista = []
    if votacion:
        lista = votacion.opciones.annotate(total_votos=Count("votos"))
    return render(request, "voting/a04_opciones.html", {
        "votaciones": votaciones, "v": votacion, "opciones": lista, "editar": request.GET.get("editar", ""),
    })


@solo_administrador
@require_POST
def admin_opcion_crear(request):
    votacion = get_object_or_404(Votacion, pk=entero(request.POST.get("votacion")))
    form = OpcionForm(request.POST, votacion=votacion)
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a04(votacion.pk))
    opcion = form.save(commit=False)
    opcion.votacion = votacion
    opcion.orden = (votacion.opciones.aggregate(m=Max("orden"))["m"] or 0) + 1
    if not opcion.descripcion:
        opcion.descripcion = "Opción nueva"
    opcion.save()
    registrar(request, f"Opción «{opcion.nombre}» agregada a «{votacion.titulo}»")
    messages.success(request, "Opción agregada.")
    return redirect(_url_a04(votacion.pk))


@solo_administrador
@require_POST
def admin_opcion_editar(request, pk):
    opcion = get_object_or_404(Opcion, pk=pk)
    anterior = opcion.nombre
    form = OpcionForm(request.POST, instance=opcion)
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a04(opcion.votacion_id, editar=pk))
    form.save()
    registrar(request, f"Opción «{opcion.nombre}» actualizada",
              detalle=f"«{anterior}» → «{opcion.nombre}»" if anterior != opcion.nombre else "")
    messages.success(request, "Cambio guardado.")
    return redirect(_url_a04(opcion.votacion_id))


@solo_administrador
@require_POST
def admin_opcion_estado(request, pk):
    """Quitar o activar una opción (RN-09, RN-10)."""
    opcion = get_object_or_404(Opcion.objects.select_related("votacion"), pk=pk)
    votacion = opcion.votacion
    volver = redirect(_url_a04(votacion.pk))
    if not opcion.activa:
        opcion.estado = Opcion.ACTIVA
        opcion.save(update_fields=["estado"])
        registrar(request, f"Opción «{opcion.nombre}» activada")
        messages.success(request, "Opción activada.")
        return volver
    if votacion.estado == Votacion.ABIERTA and votacion.opciones_activas().count() <= 2:
        messages.error(request, "Una votación abierta necesita al menos 2 opciones activas.")
        return volver
    if opcion.votos.exists():
        # RN-10: con votos no se elimina; se desactiva para conservar el historial.
        opcion.estado = Opcion.INACTIVA
        opcion.save(update_fields=["estado"])
        registrar(request, f"Opción «{opcion.nombre}» desactivada")
        messages.warning(request, "La opción tiene votos: se desactivó en lugar de eliminarse (RN-10).")
        return volver
    nombre = opcion.nombre
    opcion.delete()
    registrar(request, f"Opción «{nombre}» eliminada de «{votacion.titulo}»")
    messages.success(request, "Opción eliminada.")
    return volver


@solo_administrador
@require_POST
def admin_opcion_mover(request, pk):
    opcion = get_object_or_404(Opcion, pk=pk)
    if mover_en_orden(Opcion.objects.filter(votacion=opcion.votacion_id), opcion, request.POST.get("direccion")):
        registrar(request, f"Opción «{opcion.nombre}» reordenada")
    return redirect(_url_a04(opcion.votacion_id))
