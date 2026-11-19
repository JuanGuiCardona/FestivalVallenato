"""Regla fija: un voto por usuario, categoría y edición (retroalimentación de la Entrega 3).

Antes, el límite de votos y la periodicidad se podían configurar en cada votación, y eso
permitía más de un voto por categoría. Esta migración:

1. Comprueba que ningún usuario tenga más de un voto en la misma categoría y edición.
   Si lo hay, se detiene sin cambiar nada y explica cómo revisarlo (no borra votos).
2. Crea la restricción única voto_unico_usuario_categoria_edicion sobre
   (id_usuario, id_edicion, id_categoria) y quita la anterior.
3. Elimina las columnas que ya no se usan: periodo y numero (voto),
   max_votos_por_votante y periodicidad_voto (votacion) y sus valores por defecto (configuracion).
"""
from django.conf import settings
from django.db import migrations, models
from django.db.models import Count


def comprobar_que_no_haya_duplicados(apps, schema_editor):
    Voto = apps.get_model("voting", "Voto")
    duplicados = (Voto.objects.values("usuario_id", "edicion_id", "categoria_id")
                  .annotate(n=Count("id_voto")).filter(n__gt=1))
    if duplicados.exists():
        lista = ", ".join(f"usuario {d['usuario_id']} / categoría {d['categoria_id']} ({d['n']} votos)"
                          for d in duplicados[:10])
        raise RuntimeError(
            "Hay usuarios con más de un voto en la misma categoría y edición: " + lista + ". "
            "Revise esos votos en MySQL (tabla voto) antes de aplicar la regla fija; la migración no borra votos."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("voting", "0003_configuracion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(comprobar_que_no_haya_duplicados, migrations.RunPython.noop),
        # Primero la nueva restricción (empieza por id_usuario y sirve de índice a esa llave
        # foránea en MySQL) y después se quita la anterior.
        migrations.AddConstraint(
            model_name="voto",
            constraint=models.UniqueConstraint(
                fields=("usuario", "edicion", "categoria"),
                name="voto_unico_usuario_categoria_edicion",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="voto",
            name="voto_unico_categoria_edicion",
        ),
        migrations.RemoveField(model_name="voto", name="numero"),
        migrations.RemoveField(model_name="voto", name="periodo"),
        migrations.RemoveField(model_name="votacion", name="max_votos_por_votante"),
        migrations.RemoveField(model_name="votacion", name="periodicidad_voto"),
        migrations.RemoveField(model_name="configuracion", name="max_votos_por_defecto"),
        migrations.RemoveField(model_name="configuracion", name="periodicidad_por_defecto"),
    ]
