"""Crea los dos roles del modelo de datos: Votante y Administrador (sección 11)."""
from django.db import migrations


def crear_roles(apps, schema_editor):
    Rol = apps.get_model("accounts", "Rol")
    for nombre in ("Votante", "Administrador"):
        Rol.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(crear_roles, migrations.RunPython.noop)]
