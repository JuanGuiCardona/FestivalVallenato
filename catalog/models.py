"""Entidades Edición y Categoría (sección 11 · RN-01, RN-02).

Edición 1:N Categoría. Cada categoría pertenece a una sola edición.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Edicion(models.Model):
    ACTIVA, INACTIVA = "activa", "inactiva"
    ESTADOS = [(ACTIVA, "Activa"), (INACTIVA, "Inactiva")]

    id_edicion = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    anio = models.PositiveSmallIntegerField("año", unique=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=INACTIVA)

    class Meta:
        db_table = "edicion"
        ordering = ["-anio"]
        verbose_name = "edición"
        verbose_name_plural = "ediciones"

    def __str__(self):
        return f"{self.nombre} ({self.anio})"

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin no puede ser anterior a la de inicio."})

    @classmethod
    def vigente(cls):
        """Edición activa más reciente (la que ve el público, CU-03)."""
        return cls.objects.filter(estado=cls.ACTIVA).order_by("-anio").first()


class Categoria(models.Model):
    ACTIVA, INACTIVA = "activa", "inactiva"
    ESTADOS = [(ACTIVA, "Activa"), (INACTIVA, "Inactiva")]

    id_categoria = models.BigAutoField(primary_key=True)
    edicion = models.ForeignKey(Edicion, on_delete=models.PROTECT, db_column="id_edicion", related_name="categorias",
                                verbose_name="edición")
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField("descripción", blank=True)
    orden = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ACTIVA)

    class Meta:
        db_table = "categoria"
        ordering = ["orden", "id_categoria"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        constraints = [
            models.UniqueConstraint(fields=["edicion", "nombre"], name="categoria_unica_por_edicion"),
        ]

    def __str__(self):
        return self.nombre

    @property
    def activa(self):
        return self.estado == self.ACTIVA
