"""Entidad Registro_Auditoria (sección 11 · RF-16, RN-13, RNF-14).

Los registros no se editan ni se borran desde la interfaz.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class RegistroAuditoria(models.Model):
    id_registro = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                db_column="id_usuario", related_name="registros_auditoria")
    accion = models.CharField(max_length=255)
    fecha_hora = models.DateTimeField(default=timezone.now, db_index=True)
    detalle = models.TextField(blank=True)
    # Apoyo a RNF-04 (detección de patrones sospechosos).
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "registro_auditoria"
        ordering = ["-fecha_hora", "-id_registro"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registro de auditoría"

    def __str__(self):
        return f"{self.fecha_hora:%Y-%m-%d %H:%M} · {self.accion}"

    @property
    def autor(self):
        return self.usuario.correo if self.usuario else "sistema"
