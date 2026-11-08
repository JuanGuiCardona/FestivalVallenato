"""API de solo lectura: GET /api/categorias/ (JSON consultado en MySQL con el ORM de Django).

Devuelve las categorías activas de la edición vigente, con sus votaciones publicadas
y las opciones activas de cada una. No entrega votos ni datos personales.
"""
from datetime import datetime

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from catalog.models import Categoria, Edicion
from voting.models import Opcion, Votacion
from voting.services import sincronizar_estados

JSON_LEGIBLE = {"ensure_ascii": False, "indent": 2}


def _fecha(valor):
    """Fechas en ISO 8601; las fechas con hora, en la hora de Colombia (TIME_ZONE)."""
    if not valor:
        return None
    if isinstance(valor, datetime):
        valor = timezone.localtime(valor)
    return valor.isoformat()


def _opcion(opcion):
    return {"id": opcion.pk, "nombre": opcion.nombre, "descripcion": opcion.descripcion}


def _votacion(votacion):
    opciones = [o for o in votacion.opciones.all() if o.estado == Opcion.ACTIVA]
    return {
        "id": votacion.pk,
        "titulo": votacion.titulo,
        "estado": votacion.estado,
        "recibe_votos": votacion.recibe_votos,
        "fecha_apertura": _fecha(votacion.fecha_apertura),
        "fecha_cierre": _fecha(votacion.fecha_cierre),
        "limite": votacion.texto_limite(),
        "opciones": [_opcion(o) for o in sorted(opciones, key=lambda o: (o.orden, o.pk))],
    }


def _categoria(categoria):
    votaciones = [v for v in categoria.votaciones.all() if v.estado != Votacion.BORRADOR]
    datos = [_votacion(v) for v in votaciones]
    return {
        "id": categoria.pk,
        "nombre": categoria.nombre,
        "descripcion": categoria.descripcion,
        "estado": categoria.estado,
        "votaciones": datos,
        # Todas las opciones de la categoría en una sola lista (útil para consumir la API).
        "opciones": [dict(o, id_votacion=v["id"]) for v in datos for o in v["opciones"]],
    }


def _edicion(edicion):
    return {"id": edicion.pk, "nombre": edicion.nombre, "anio": edicion.anio,
            "fecha_inicio": _fecha(edicion.fecha_inicio), "fecha_fin": _fecha(edicion.fecha_fin)}


def _categorias_publicas(edicion):
    return (Categoria.objects.filter(edicion=edicion, estado=Categoria.ACTIVA)
            .prefetch_related("votaciones__opciones"))


@require_GET
def categorias(request):
    """GET /api/categorias/ · categorías de la edición vigente con sus votaciones y opciones."""
    sincronizar_estados(request)
    edicion = Edicion.vigente()
    if edicion is None:
        return JsonResponse({"edicion": None, "total_categorias": 0, "categorias": []},
                            json_dumps_params=JSON_LEGIBLE)
    lista = [_categoria(c) for c in _categorias_publicas(edicion)]
    return JsonResponse({"edicion": _edicion(edicion), "total_categorias": len(lista), "categorias": lista},
                        json_dumps_params=JSON_LEGIBLE)


@require_GET
def categoria(request, pk):
    """GET /api/categorias/<id>/ · una categoría activa de la edición vigente."""
    sincronizar_estados(request)
    edicion = Edicion.vigente()
    obj = _categorias_publicas(edicion).filter(pk=pk).first() if edicion else None
    if obj is None:
        return JsonResponse({"error": "La categoría no existe o no está publicada."}, status=404,
                            json_dumps_params=JSON_LEGIBLE)
    return JsonResponse({"edicion": _edicion(edicion), **_categoria(obj)}, json_dumps_params=JSON_LEGIBLE)
