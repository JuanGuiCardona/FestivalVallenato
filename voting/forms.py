"""Formularios de gestión de votaciones (CU-07) y opciones (CU-08)."""
from django import forms

from catalog.models import Categoria

from .models import Opcion, Votacion

FORMATO_FECHA_HORA = "%Y-%m-%dT%H:%M"


class CategoriaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.edicion.anio} · {obj.nombre}"


class VotacionNuevaForm(forms.ModelForm):
    """Alta rápida del prototipo: título + categoría. Queda en borrador (CU-07 paso 4)."""
    categoria = CategoriaChoiceField(label="Categoría", queryset=Categoria.objects.select_related("edicion"),
                                     error_messages={"required": "Elige la categoría.",
                                                     "invalid_choice": "Elige una categoría válida."})

    class Meta:
        model = Votacion
        fields = ["titulo", "categoria"]
        error_messages = {"titulo": {"required": "Escribe el título de la votación."}}


class VotacionConfigForm(forms.ModelForm):
    """Configurar título, categoría, fechas y reglas (RF-13 · RNF-16)."""
    categoria = CategoriaChoiceField(label="Categoría", queryset=Categoria.objects.select_related("edicion"))

    # Con votos registrados solo se permiten cambios no críticos (CU-07 2a, propuesta*).
    CAMPOS_CRITICOS = ["categoria", "fecha_apertura", "max_votos_por_votante", "periodicidad_voto"]

    class Meta:
        model = Votacion
        fields = ["titulo", "categoria", "descripcion", "fecha_apertura", "fecha_cierre",
                  "max_votos_por_votante", "periodicidad_voto", "resultados_visibles"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "fecha_apertura": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=FORMATO_FECHA_HORA),
            "fecha_cierre": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=FORMATO_FECHA_HORA),
            "max_votos_por_votante": forms.NumberInput(attrs={"min": 1, "max": 50}),
        }
        error_messages = {"titulo": {"required": "Escribe el título de la votación."}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_apertura"].input_formats = [FORMATO_FECHA_HORA, "%Y-%m-%d %H:%M"]
        self.fields["fecha_cierre"].input_formats = [FORMATO_FECHA_HORA, "%Y-%m-%d %H:%M"]
        self.bloqueados = []
        if self.instance.pk and self.instance.tiene_votos():
            for nombre in self.CAMPOS_CRITICOS:
                self.fields[nombre].disabled = True
                self.bloqueados.append(nombre)


class OpcionForm(forms.ModelForm):
    class Meta:
        model = Opcion
        fields = ["nombre", "descripcion"]
        error_messages = {"nombre": {"required": "Escribe el nombre de la opción."}}

    def __init__(self, *args, votacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.votacion = votacion or getattr(self.instance, "votacion", None)

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetida = Opcion.objects.filter(votacion=self.votacion, nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if repetida.exists():
            raise forms.ValidationError("Ya existe una opción con ese nombre en esta votación.")
        return nombre
