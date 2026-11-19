"""Simulación de votos simultáneos contra la base de datos configurada (MySQL).

La usan la prueba automática de concurrencia y el comando `python manage.py simular_votacion`.
Cada intento corre en su propio hilo con su propia conexión a MySQL, y todos arrancan
al mismo tiempo (threading.Barrier), como si muchos votantes pulsaran «Confirmar voto» a la vez.
"""
import threading
import time
from collections import Counter

from django.db import OperationalError, connection
from django.db.models import Count
from django.test import RequestFactory

from . import services
from .models import Voto


def simular(usuarios, votaciones, intentos_por_usuario=3):
    """Lanza `intentos_por_usuario` votos simultáneos de cada usuario.

    Los intentos de un mismo usuario se reparten entre las votaciones dadas (que deben ser
    de la misma categoría), para probar también el duplicado entre votaciones distintas.
    Devuelve un diccionario con el resumen.
    """
    tareas = []
    for usuario in usuarios:
        for i in range(intentos_por_usuario):
            votacion = votaciones[i % len(votaciones)]
            tareas.append((usuario, votacion, votacion.opciones.filter(estado="activa").first()))

    barrera = threading.Barrier(len(tareas))
    resultados = Counter()
    errores = []
    candado = threading.Lock()

    def intentar(usuario, votacion, opcion):
        request = RequestFactory().post("/", REMOTE_ADDR="127.0.0.1")
        request.user = usuario
        try:
            barrera.wait()
            services.emitir_voto(request, votacion.pk, opcion.pk)
            clave = "registrado"
        except services.ReglaVoto as e:
            clave = f"rechazado: {e.codigo}"
        except OperationalError as e:
            # Límite de capacidad de MySQL (por ejemplo, 1040 «Too many connections»), no de la regla.
            clave = "sin conexión disponible" if e.args and e.args[0] == 1040 else "error"
            if clave == "error":
                with candado:
                    errores.append(repr(e))
        except Exception as e:  # cualquier otro error se informa, no se oculta
            clave = "error"
            with candado:
                errores.append(repr(e))
        finally:
            connection.close()
        with candado:
            resultados[clave] += 1

    hilos = [threading.Thread(target=intentar, args=t) for t in tareas]
    inicio = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    duracion = time.perf_counter() - inicio

    categoria = votaciones[0].categoria
    votos = Voto.objects.filter(usuario__in=usuarios, categoria=categoria)
    por_usuario = votos.values("usuario").annotate(n=Count("id_voto"))
    return {
        "usuarios": len(usuarios),
        "solicitudes": len(tareas),
        "resultados": dict(resultados),
        "votos_guardados": votos.count(),
        "usuarios_con_mas_de_un_voto": sum(1 for f in por_usuario if f["n"] > 1),
        "usuarios_sin_voto": len(usuarios) - por_usuario.count(),
        "errores": errores,
        "segundos": duracion,
    }
