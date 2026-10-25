"""Formularios de la gestión de ediciones y categorías (CU-06)."""
from django import forms

from .models import Categoria, Edicion


class EdicionForm(forms.ModelForm):
    class Meta:
        model = Edicion
        fields = ["nombre", "anio", "fecha_inicio", "fecha_fin"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        error_messages = {
            "nombre": {"required": "Escribe el nombre de la edición."},
            "anio": {"required": "Escribe el año de la edición.", "unique": "Ya existe una edición de ese año."},
        }


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]
        error_messages = {"nombre": {"required": "Escribe el nombre de la categoría."}}

    def __init__(self, *args, edicion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.edicion = edicion or getattr(self.instance, "edicion", None)

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetida = Categoria.objects.filter(edicion=self.edicion, nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if repetida.exists():
            # CU-06 5a: nombre duplicado.
            raise forms.ValidationError("Ya existe una categoría con ese nombre.")
        return nombre


def primer_error(form):
    for lista in form.errors.values():
        if lista:
            return lista[0]
    return "Revisa los datos."
