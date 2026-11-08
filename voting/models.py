"""Entidades Votación, Opción y Voto (sección 11 · RN-01 a RN-11).

Las reglas que todavía no confirma el cliente son atributos de la votación,
no código fijo (11.2 «Configurabilidad», RNF-16). Sus valores por defecto son
PRELIMINARES*: un voto, una única vez, resultados al cierre.
"""
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from catalog.models import Categoria, Edicion


class Votacion(models.Model):
    BORRADOR, PROXIMA, ABIERTA, CERRADA = "borrador", "proxima", "abierta", "cerrada"
    ESTADOS = [(BORRADOR, "Borrador"), (PROXIMA, "Próximamente"), (ABIERTA, "Abierta"), (CERRADA, "Cerrada")]

    # RN-06 (pendiente de validación*): frecuencia del voto.
    UNICA, DIARIA = "unica", "diaria"
    PERIODICIDADES = [(UNICA, "Una única vez durante la votación"), (DIARIA, "Cada día (se reinicia a medianoche)")]

    # RN-11 (pendiente de validación*): visibilidad de resultados.
    RES_VIVO, RES_CIERRE, RES_ADMIN = "vivo", "cierre", "admin"
    VISIBILIDADES = [
        (RES_VIVO, "En vivo, durante la votación"),
        (RES_CIERRE, "Al cierre de la votación"),
        (RES_ADMIN, "Solo para administradores"),
    ]

    id_votacion = models.BigAutoField(primary_key=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column="id_categoria", related_name="votaciones",
                                  verbose_name="categoría")
    titulo = models.CharField("título", max_length=160)
    descripcion = models.TextField("descripción", blank=True)
    fecha_apertura = models.DateTimeField("fecha de apertura", null=True, blank=True)
    fecha_cierre = models.DateTimeField("fecha de cierre", null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=BORRADOR)
    max_votos_por_votante = models.PositiveSmallIntegerField("máximo de votos por votante", default=1)
    periodicidad_voto = models.CharField("periodicidad del voto", max_length=10, choices=PERIODICIDADES, default=UNICA)
    resultados_visibles = models.CharField("resultados visibles", max_length=10, choices=VISIBILIDADES, default=RES_CIERRE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "votacion"
        ordering = ["categoria__orden", "id_votacion"]
        verbose_name = "votación"
        verbose_name_plural = "votaciones"
        indexes = [models.Index(fields=["estado"], name="votacion_estado_idx")]

    def __str__(self):
        return self.titulo

    # ---------------------------------------------------------- validaciones
    def clean(self):
        # CU-07 4a: el cierre no puede ser anterior a la apertura.
        if self.fecha_apertura and self.fecha_cierre and self.fecha_cierre <= self.fecha_apertura:
            raise ValidationError({"fecha_cierre": "La fecha de cierre debe ser posterior a la de apertura."})
        if self.max_votos_por_votante < 1:
            raise ValidationError({"max_votos_por_votante": "Debe permitir al menos 1 voto."})

    # ---------------------------------------------------------- estado
    def opciones_activas(self):
        return self.opciones.filter(estado=Opcion.ACTIVA)

    def sincronizar_estado(self):
        """Apertura y cierre programados por fechas (RN-04, CU-07 pasos 5 y 6).

        Devuelve el texto de la acción realizada (para auditoría) o None.
        """
        ahora = timezone.now()
        accion = None
        if (self.estado == self.PROXIMA and self.fecha_apertura and ahora >= self.fecha_apertura
                and self.opciones_activas().count() >= 2):
            self.estado = self.ABIERTA
            accion = f"Apertura programada de «{self.titulo}»"
        if self.estado == self.ABIERTA and self.fecha_cierre and ahora >= self.fecha_cierre:
            self.estado = self.CERRADA
            accion = f"Cierre programado de «{self.titulo}»"
        if accion:
            self.save(update_fields=["estado"])
        return accion

    @property
    def recibe_votos(self):
        """RN-04: abierta y con la fecha actual dentro de su ventana."""
        ahora = timezone.now()
        if self.estado != self.ABIERTA:
            return False
        if self.fecha_apertura and ahora < self.fecha_apertura:
            return False
        if self.fecha_cierre and ahora >= self.fecha_cierre:
            return False
        return True

    @property
    def resultados_publicos(self):
        """RN-11 / RF-10: ¿puede el público ver los resultados?"""
        if self.resultados_visibles == self.RES_ADMIN or self.estado == self.BORRADOR:
            return False
        if self.estado == self.CERRADA:
            return True
        return self.resultados_visibles == self.RES_VIVO

    def tiene_votos(self):
        return self.votos.exists()

    # ---------------------------------------------------------- reglas del voto
    def periodo_actual(self):
        """Periodo usado en la restricción única del voto (11.2)."""
        if self.periodicidad_voto == self.DIARIA:
            return timezone.localdate().isoformat()
        return "UNICA"

    def texto_limite(self):
        n = self.max_votos_por_votante
        votos = "1 voto" if n == 1 else f"{n} votos"
        cuando = "por día" if self.periodicidad_voto == self.DIARIA else "por persona"
        return f"{votos} {cuando} en la categoría"


class Opcion(models.Model):
    ACTIVA, INACTIVA = "activa", "inactiva"
    ESTADOS = [(ACTIVA, "Activa"), (INACTIVA, "Inactiva")]

    id_opcion = models.BigAutoField(primary_key=True)
    votacion = models.ForeignKey(Votacion, on_delete=models.PROTECT, db_column="id_votacion", related_name="opciones",
                                 verbose_name="votación")
    nombre = models.CharField(max_length=160)
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    orden = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ACTIVA)

    class Meta:
        db_table = "opcion"
        ordering = ["orden", "id_opcion"]
        verbose_name = "opción"
        verbose_name_plural = "opciones"
        constraints = [
            # CU-08 4a: no hay dos opciones con el mismo nombre en una votación.
            models.UniqueConstraint(fields=["votacion", "nombre"], name="opcion_unica_por_votacion"),
        ]

    def __str__(self):
        return self.nombre

    @property
    def activa(self):
        return self.estado == self.ACTIVA


def nuevo_codigo():
    """Código de comprobante (RF-09; idea del número de seguimiento de Helios)."""
    return "FV27-" + secrets.token_hex(4).upper()


class Voto(models.Model):
    REGISTRADO, ANULADO = "registrado", "anulado"
    ESTADOS = [(REGISTRADO, "Registrado"), (ANULADO, "Anulado")]

    id_voto = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="id_usuario", related_name="votos")
    votacion = models.ForeignKey(Votacion, on_delete=models.PROTECT, db_column="id_votacion", related_name="votos")
    opcion = models.ForeignKey(Opcion, on_delete=models.PROTECT, db_column="id_opcion", related_name="votos")
    # Regla de unicidad del enunciado: un voto por usuario, categoría y edición.
    # Se copian de la votación al guardar, para que MySQL pueda exigir la regla.
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column="id_categoria",
                                  related_name="votos", editable=False)
    edicion = models.ForeignKey(Edicion, on_delete=models.PROTECT, db_column="id_edicion",
                                related_name="votos", editable=False)
    fecha_hora = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=REGISTRADO)
    # Apoyo a la regla de unicidad (11.2): periodo = "UNICA" o la fecha del día;
    # numero = 1..máximo de votos por votante en la categoría y ese periodo.
    periodo = models.CharField(max_length=10)
    numero = models.PositiveSmallIntegerField(default=1)
    codigo = models.CharField("código de comprobante", max_length=20, unique=True, default=nuevo_codigo)

    class Meta:
        db_table = "voto"
        ordering = ["-fecha_hora"]
        verbose_name = "voto"
        verbose_name_plural = "votos"
        constraints = [
            # Un voto por usuario, categoría y edición (RN-06, RNF-05 / R-07). MySQL impide
            # el duplicado aunque las solicitudes lleguen al mismo tiempo o desde dos sesiones.
            models.UniqueConstraint(fields=["usuario", "edicion", "categoria", "periodo", "numero"],
                                    name="voto_unico_categoria_edicion"),
        ]
        indexes = [models.Index(fields=["votacion", "opcion"], name="voto_conteo_idx")]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        # 11.2 «Coherencia de la opción»: la opción debe ser de la misma votación.
        if self.opcion.votacion_id != self.votacion_id:
            raise ValidationError("La opción no pertenece a esta votación.")
        # La categoría y la edición siempre son las de la votación.
        self.categoria_id = self.votacion.categoria_id
        self.edicion_id = self.votacion.categoria.edicion_id
        super().save(*args, **kwargs)


class Configuracion(models.Model):
    """A-06 Configuración general: valores que el administrador cambia desde la interfaz.

    Hay una sola fila. Mientras no se guarde, se usan los valores del archivo .env
    (LOGIN_MAX_INTENTOS, LOGIN_BLOQUEO_SEGUNDOS, VOTOS_MAX_POR_MINUTO) y los valores
    por defecto de la votación.
    """
    id_configuracion = models.AutoField(primary_key=True)
    # Seguridad (RNF-04, preliminar*)
    max_intentos_login = models.PositiveSmallIntegerField("intentos de inicio de sesión antes del bloqueo", default=5)
    minutos_bloqueo = models.PositiveSmallIntegerField("minutos de bloqueo temporal", default=5)
    votos_por_minuto = models.PositiveSmallIntegerField("solicitudes de voto por minuto por persona", default=10)
    # Valores con los que se crean las votaciones nuevas (RN-06, RN-11, preliminares*)
    max_votos_por_defecto = models.PositiveSmallIntegerField("votos por persona en cada categoría", default=1)
    periodicidad_por_defecto = models.CharField("periodicidad del voto", max_length=10,
                                                choices=Votacion.PERIODICIDADES, default=Votacion.UNICA)
    resultados_por_defecto = models.CharField("resultados visibles", max_length=10,
                                              choices=Votacion.VISIBILIDADES, default=Votacion.RES_CIERRE)
    fecha_actualizacion = models.DateTimeField("última actualización", auto_now=True)

    class Meta:
        db_table = "configuracion"
        verbose_name = "configuración general"
        verbose_name_plural = "configuración general"

    def __str__(self):
        return "Configuración general"

    @classmethod
    def actual(cls):
        """La configuración guardada o, si no hay, una con los valores del .env (sin guardar)."""
        guardada = cls.objects.first()
        if guardada:
            return guardada
        return cls(
            max_intentos_login=settings.LOGIN_MAX_INTENTOS,
            minutos_bloqueo=max(1, settings.LOGIN_BLOQUEO_SEGUNDOS // 60),
            votos_por_minuto=settings.VOTOS_MAX_POR_MINUTO,
        )
