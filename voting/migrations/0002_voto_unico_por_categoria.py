"""Regla de unicidad del enunciado: un voto por usuario, categoría y edición.

1. Agrega a `voto` las columnas id_categoria e id_edicion (llaves foráneas).
2. Las llena en los votos que ya existen, a partir de su votación.
3. Renumera los votos de cada usuario dentro de su categoría, para que los datos
   anteriores cumplan la nueva restricción (no se borra ningún voto).
4. Crea la restricción única voto_unico_categoria_edicion y quita la anterior,
   que era por votación.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def llenar_categoria_y_edicion(apps, schema_editor):
    Voto = apps.get_model("voting", "Voto")
    grupos = {}
    for voto in Voto.objects.select_related("votacion__categoria").order_by("fecha_hora", "id_voto"):
        voto.categoria_id = voto.votacion.categoria_id
        voto.edicion_id = voto.votacion.categoria.edicion_id
        clave = (voto.usuario_id, voto.edicion_id, voto.categoria_id, voto.periodo)
        grupos.setdefault(clave, []).append(voto)
    # Dos pasadas para no chocar con la restricción anterior mientras se renumera.
    for votos in grupos.values():
        for n, voto in enumerate(votos, start=1):
            voto.numero = 10000 + n
            voto.save(update_fields=["categoria", "edicion", "numero"])
    for votos in grupos.values():
        for n, voto in enumerate(votos, start=1):
            voto.numero = n
            voto.save(update_fields=["numero"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("voting", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="voto",
            name="categoria",
            field=models.ForeignKey(db_column="id_categoria", editable=False, null=True,
                                    on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="catalog.categoria"),
        ),
        migrations.AddField(
            model_name="voto",
            name="edicion",
            field=models.ForeignKey(db_column="id_edicion", editable=False, null=True,
                                    on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="catalog.edicion"),
        ),
        migrations.RunPython(llenar_categoria_y_edicion, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="voto",
            name="categoria",
            field=models.ForeignKey(db_column="id_categoria", editable=False,
                                    on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="catalog.categoria"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="edicion",
            field=models.ForeignKey(db_column="id_edicion", editable=False,
                                    on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="catalog.edicion"),
        ),
        # Primero la nueva (empieza por id_usuario y sirve de índice a esa llave foránea en MySQL)
        # y después se quita la anterior.
        migrations.AddConstraint(
            model_name="voto",
            constraint=models.UniqueConstraint(fields=("usuario", "edicion", "categoria", "periodo", "numero"),
                                               name="voto_unico_categoria_edicion"),
        ),
        migrations.RemoveConstraint(
            model_name="voto",
            name="voto_unico_por_periodo",
        ),
    ]
