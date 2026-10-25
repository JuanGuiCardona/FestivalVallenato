"""Cálculo de resultados (CU-05, CU-09 · RF-10, RF-15): conteo, porcentaje y total."""
from django.db.models import Count, Q

from voting.models import Voto


def calcular(votacion):
    """Devuelve (filas, total). Cuenta solo votos con estado «registrado»."""
    opciones = votacion.opciones.annotate(n=Count("votos", filter=Q(votos__estado=Voto.REGISTRADO)))
    total = sum(o.n for o in opciones)
    maximo = max((o.n for o in opciones), default=0)
    filas = [{
        "nombre": o.nombre,
        "activa": o.activa,
        "votos": o.n,
        # Igual que el prototipo: porcentaje redondeado a entero.
        "porcentaje": round(o.n * 100 / total) if total else 0,
        "lider": maximo > 0 and o.n == maximo,
    } for o in opciones]
    return filas, total
