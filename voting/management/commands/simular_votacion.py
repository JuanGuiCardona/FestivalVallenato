"""Prueba de concurrencia directamente sobre la base de datos configurada (MySQL).

Uso:
    python manage.py simular_votacion                  # 30 votantes, 3 intentos simultáneos cada uno
    python manage.py simular_votacion --usuarios 60 --intentos 4
    python manage.py simular_votacion --conservar      # no borra los datos de la simulación

Crea votantes temporales, hace que todos intenten votar al mismo tiempo en una votación
abierta (y en otra de la misma categoría, si existe) y comprueba en MySQL que cada votante
quedó con un solo voto en la categoría. Al terminar borra los votantes y votos de la
simulación, salvo que se use --conservar.
"""
import uuid

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from accounts.models import Usuario
from audit.models import RegistroAuditoria
from catalog.models import Edicion
from voting.models import Configuracion, Votacion, Voto
from voting.services import sincronizar_estados
from voting.simulacion import simular

DOMINIO = "simulacion.local"


class Command(BaseCommand):
    help = "Simula muchos votantes votando a la vez y verifica en la base de datos la regla de un voto por categoría."

    def add_arguments(self, parser):
        parser.add_argument("--usuarios", type=int, default=30, help="Votantes simultáneos (por defecto 30).")
        parser.add_argument("--intentos", type=int, default=3, help="Intentos simultáneos por votante (por defecto 3).")
        parser.add_argument("--votacion", type=int, help="Id de la votación (por defecto, la primera abierta).")
        parser.add_argument("--conservar", action="store_true", help="No borrar los datos de la simulación.")

    def handle(self, *args, **opciones):
        n_usuarios, intentos = opciones["usuarios"], opciones["intentos"]
        if not 1 <= n_usuarios <= 200 or not 1 <= intentos <= 10:
            raise CommandError("Use entre 1 y 200 usuarios y entre 1 y 10 intentos por usuario.")
        votaciones = self._votaciones(opciones.get("votacion"))
        motor = connection.vendor
        if motor == "sqlite":
            self.stdout.write(self.style.WARNING(
                "Está usando SQLite (modo demostración). La simulación sirve de verdad con MySQL."))

        self.stdout.write(f"Base de datos: {motor} · {connection.settings_dict.get('NAME')}")
        if motor == "mysql":
            self._revisar_conexiones(n_usuarios * intentos)
        self.stdout.write(f"Votación: «{votaciones[0].titulo}» · categoría «{votaciones[0].categoria.nombre}»"
                          + (f" (y «{votaciones[1].titulo}», de la misma categoría)" if len(votaciones) > 1 else ""))
        self.stdout.write(f"Lanzando {n_usuarios} votantes × {intentos} intentos = {n_usuarios * intentos} "
                          "solicitudes al mismo tiempo…\n")

        lote = uuid.uuid4().hex[:6]
        usuarios = [Usuario.objects.create_user(correo=f"sim-{lote}-{i}@{DOMINIO}", password=None,
                                                nombre=f"Votante simulado {i}", acepta_datos=True)
                    for i in range(1, n_usuarios + 1)]
        # La simulación no debe chocar con el freno de solicitudes por minuto de cada votante.
        config = Configuracion.actual()
        original = config.votos_por_minuto
        cache.clear()
        try:
            if config.pk:
                Configuracion.objects.filter(pk=config.pk).update(votos_por_minuto=max(original, intentos + 1))
            resumen = simular(usuarios, votaciones, intentos)
        finally:
            if config.pk:
                Configuracion.objects.filter(pk=config.pk).update(votos_por_minuto=original)
            if not opciones["conservar"]:
                self._limpiar(usuarios)

        self._informe(resumen, opciones["conservar"])

    def _votaciones(self, pk):
        sincronizar_estados()
        if pk:
            votacion = Votacion.objects.select_related("categoria").filter(pk=pk).first()
            if not votacion or not votacion.recibe_votos:
                raise CommandError("Esa votación no existe o no está abierta.")
        else:
            edicion = Edicion.vigente()
            abiertas = [v for v in Votacion.objects.select_related("categoria")
                        .filter(estado=Votacion.ABIERTA, categoria__edicion=edicion) if v.recibe_votos]
            if not abiertas:
                raise CommandError("No hay votaciones abiertas en la edición vigente. Abra una desde el panel (A-03).")
            votacion = abiertas[0]
        hermanas = [v for v in Votacion.objects.filter(categoria=votacion.categoria, estado=Votacion.ABIERTA)
                    .exclude(pk=votacion.pk) if v.recibe_votos]
        return [votacion] + hermanas[:1]

    def _revisar_conexiones(self, solicitudes):
        """Cada solicitud simultánea usa su propia conexión: no pueden superar el máximo de MySQL."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@max_connections")
            maximo = cursor.fetchone()[0]
            cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
            en_uso = int(cursor.fetchone()[1])
        disponibles = maximo - en_uso - 5
        self.stdout.write(f"Conexiones de MySQL: máximo {maximo}, en uso {en_uso}, disponibles {disponibles}")
        if solicitudes > disponibles:
            raise CommandError(
                f"La simulación abriría {solicitudes} conexiones al mismo tiempo y MySQL solo tiene {disponibles} "
                f"disponibles (max_connections = {maximo}). Use menos solicitudes, por ejemplo "
                f"--usuarios {max(1, disponibles // 4)} --intentos 4, o aumente max_connections en MySQL "
                "(en un servidor se recomienda 200 o más; ver DESPLIEGUE.md).")

    def _limpiar(self, usuarios):
        ids = [u.pk for u in usuarios]
        Voto.objects.filter(usuario_id__in=ids).delete()
        RegistroAuditoria.objects.filter(usuario_id__in=ids).delete()
        Usuario.objects.filter(pk__in=ids).delete()

    def _informe(self, r, conservar):
        w = self.stdout.write
        w("Resultado")
        w("---------")
        w(f"Votantes simultáneos:            {r['usuarios']}")
        w(f"Solicitudes enviadas a la vez:   {r['solicitudes']}")
        for clave, n in sorted(r["resultados"].items()):
            w(f"  {clave:<30} {n}")
        w(f"Votos guardados en la base:      {r['votos_guardados']}")
        w(f"Votantes con más de un voto:     {r['usuarios_con_mas_de_un_voto']}")
        w(f"Votantes sin voto:               {r['usuarios_sin_voto']}")
        w(f"Tiempo total:                    {r['segundos']:.2f} s "
          f"({r['solicitudes'] / r['segundos']:.0f} solicitudes por segundo)")
        for e in r["errores"][:5]:
            w(self.style.ERROR(f"Error: {e}"))
        sin_conexion = r["resultados"].get("sin conexión disponible", 0)
        if sin_conexion:
            w(self.style.WARNING(f"\n{sin_conexion} solicitudes no obtuvieron conexión: MySQL alcanzó su máximo "
                                 "de conexiones. Es un límite de capacidad del servidor, no de la regla del voto."))
        correcto = (r["votos_guardados"] == r["usuarios"] and r["usuarios_con_mas_de_un_voto"] == 0
                    and not r["errores"] and not sin_conexion)
        if correcto:
            w(self.style.SUCCESS(f"\nOK: cada votante quedó con exactamente 1 voto en la categoría; "
                                 f"se rechazaron {r['solicitudes'] - r['votos_guardados']} duplicados."))
        else:
            w(self.style.ERROR("\nFALLÓ: la regla de un voto por categoría no se cumplió. Revise los datos."))
        w("Datos de la simulación conservados." if conservar else "Datos de la simulación borrados.")
