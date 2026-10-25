"""Formularios de registro (CU-01) e inicio de sesión (CU-02).

Los mensajes son los mismos del prototipo. Se muestra el primer error
encontrado, en el mismo orden en que el prototipo los revisaba.
"""
import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Usuario

CORREO_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


class RegistroForm(forms.Form):
    nombre = forms.CharField(required=False, max_length=150)
    correo = forms.CharField(required=False, max_length=254)
    clave = forms.CharField(required=False, strip=False)
    clave2 = forms.CharField(required=False, strip=False)
    ciudad = forms.CharField(required=False, max_length=120)  # dato por validar*
    acepta = forms.BooleanField(required=False)

    def clean(self):
        d = super().clean()
        nombre = (d.get("nombre") or "").strip()
        correo = (d.get("correo") or "").strip().lower()
        clave, clave2 = d.get("clave") or "", d.get("clave2") or ""

        if len(nombre) < 3:
            raise ValidationError("Escribe tu nombre completo.")
        if not CORREO_RE.match(correo):
            raise ValidationError("Escribe un correo válido, por ejemplo nombre@correo.com.")
        if len(clave) < 8:
            raise ValidationError("La contraseña debe tener al menos 8 caracteres.")
        if clave != clave2:
            raise ValidationError("Las contraseñas no coinciden.")
        if not d.get("acepta"):
            raise ValidationError("Debes aceptar el tratamiento de datos personales para crear la cuenta (RN-12).")
        if Usuario.objects.filter(correo__iexact=correo).exists():
            raise ValidationError("Ese correo ya está registrado. Inicia sesión con él (RN-14).")
        # CU-01 paso 4: fortaleza de la contraseña con los validadores de Django.
        validate_password(clave, Usuario(nombre=nombre, correo=correo))

        d["nombre"], d["correo"] = nombre, correo
        d["ciudad"] = (d.get("ciudad") or "").strip()
        return d

    @property
    def primer_error(self):
        errores = self.non_field_errors() or [e for lista in self.errors.values() for e in lista]
        return errores[0] if errores else ""


class LoginForm(forms.Form):
    correo = forms.CharField(required=False, max_length=254)
    clave = forms.CharField(required=False, strip=False)

    def clean_correo(self):
        return (self.cleaned_data.get("correo") or "").strip().lower()
