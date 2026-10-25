"""Ordenar elementos con las flechas ↑ ↓ (RF-12 y RF-14: «ordenar»)."""
from django.db import transaction


def mover_en_orden(queryset, objeto, direccion):
    """Intercambia el `orden` de `objeto` con su vecino. Devuelve True si se movió."""
    with transaction.atomic():
        elementos = list(queryset.select_for_update())
        # Normaliza el orden (0, 1, 2, ...) por si había valores repetidos.
        for i, el in enumerate(elementos):
            if el.orden != i:
                el.orden = i
                el.save(update_fields=["orden"])
        pos = next((i for i, el in enumerate(elementos) if el.pk == objeto.pk), None)
        destino = None if pos is None else pos + (-1 if direccion == "subir" else 1)
        if destino is None or not 0 <= destino < len(elementos):
            return False
        a, b = elementos[pos], elementos[destino]
        a.orden, b.orden = b.orden, a.orden
        a.save(update_fields=["orden"])
        b.save(update_fields=["orden"])
        return True


def entero(valor):
    """Convierte a número un parámetro de la dirección o del formulario; si no es válido, None."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None
