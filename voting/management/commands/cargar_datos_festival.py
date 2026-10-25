"""python manage.py cargar_datos_festival [--demo]

Carga la edición 2027 con las categorías, votaciones y opciones del prototipo
(sin votos). Con --demo crea además las cuentas de prueba. Se puede ejecutar
varias veces: no duplica nada.

Los datos son ILUSTRATIVOS (12.6 del documento): las categorías definitivas
están pendientes de validación con el cliente.
"""
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Rol, Usuario
from catalog.models import Categoria, Edicion
from voting.models import Opcion, Votacion


def fecha(anio, mes, dia, hora, minuto=0):
    return timezone.make_aware(datetime(anio, mes, dia, hora, minuto))


class Command(BaseCommand):
    help = "Carga los datos de ejemplo del prototipo (edición 2027)."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Crea las cuentas de prueba del prototipo.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        ahora = timezone.now()
        edicion, _ = Edicion.objects.get_or_create(
            anio=2027,
            defaults={"nombre": "60° Festival de la Leyenda Vallenata", "fecha_inicio": date(2027, 4, 28),
                      "fecha_fin": date(2027, 5, 1), "estado": Edicion.ACTIVA},
        )
        if not Edicion.objects.filter(estado=Edicion.ACTIVA).exists():
            edicion.estado = Edicion.ACTIVA
            edicion.save(update_fields=["estado"])

        # (categoría, [(título, descripción, estado, apertura, cierre, resultados, periodicidad, opciones)])
        datos = [
            ("Música", [
                ("Canción favorita del público", "Elige la canción inédita que más te hizo vibrar en la tarima.",
                 "abierta", ahora, fecha(2027, 5, 1, 20), "vivo", "unica",
                 [("Canción A", "Paseo inédito"), ("Canción B", "Merengue inédito"), ("Canción C", "Son inédito")]),
                ("Mejor presentación en tarima", "Vota por la presentación que más te emocionó.",
                 "proxima", fecha(2027, 4, 28, 10), fecha(2027, 5, 2, 18), "cierre", "unica",
                 [("Presentación A", "Escenario principal"), ("Presentación B", "Parque de la Leyenda")]),
            ]),
            ("Danza y comparsas", [
                ("Mejor vestuario de piloneras", "Reconoce el vestuario más vistoso del desfile.",
                 "abierta", ahora, fecha(2027, 4, 30, 21), "cierre", "unica",
                 [("Vestuario A", "Piloneras mayores"), ("Vestuario B", "Piloneras juveniles"), ("Vestuario C", "Piloneras infantiles")]),
                ("Comparsa más animada", "La comparsa que más puso a bailar al público.",
                 "cerrada", ahora - timedelta(days=7), ahora - timedelta(minutes=1), "vivo", "unica",
                 [("Comparsa A", "Desfile de Piloneras"), ("Comparsa B", "Desfile de Jeep Willys"), ("Comparsa C", "Plaza Alfonso López")]),
            ]),
            ("Piquería", [
                ("Verso más ingenioso", "El verso improvisado que mejor te hizo reír o pensar.",
                 "abierta", ahora, fecha(2027, 5, 1, 17), "cierre", "diaria",
                 [("Verso A", "Piquería mayor"), ("Verso B", "Piquería infantil")]),
            ]),
            ("Eventos del Festival", [
                ("Foto favorita del Festival", "Votación en preparación.",
                 "borrador", None, None, "cierre", "unica", [("Foto A", "Álbum oficial")]),
            ]),
        ]
        for i, (nombre_cat, votaciones) in enumerate(datos):
            categoria, _ = Categoria.objects.get_or_create(edicion=edicion, nombre=nombre_cat, defaults={"orden": i})
            for titulo, desc, estado, apertura, cierre, res, periodicidad, opts in votaciones:
                votacion, creada = Votacion.objects.get_or_create(
                    categoria=categoria, titulo=titulo,
                    defaults={"descripcion": desc, "estado": estado, "fecha_apertura": apertura, "fecha_cierre": cierre,
                              "resultados_visibles": res, "periodicidad_voto": periodicidad},
                )
                for j, (nom, d) in enumerate(opts):
                    Opcion.objects.get_or_create(votacion=votacion, nombre=nom, defaults={"descripcion": d, "orden": j})
                self.stdout.write(f"  {'+' if creada else '='} {titulo}")

        if opciones["demo"]:
            cuentas = [
                ("votante@demo.co", "demo1234", "Votante Demo", Rol.VOTANTE, False),
                ("admin@demo.co", "admin1234", "Administración del Festival", Rol.ADMINISTRADOR, True),
            ]
            for correo, clave, nombre, rol, superusuario in cuentas:
                if not Usuario.objects.filter(correo=correo).exists():
                    u = Usuario(correo=correo, nombre=nombre, rol=Rol.obtener(rol), is_superuser=superusuario,
                                acepta_datos=True, fecha_aceptacion=ahora)
                    u.set_password(clave)
                    u.save()
                self.stdout.write(f"  cuenta {correo} / {clave}")
        self.stdout.write(self.style.SUCCESS("Datos del Festival cargados."))
