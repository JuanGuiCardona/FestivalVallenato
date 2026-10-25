"""Pantallas P-01 Inicio, P-04 Categorías (CU-03) y A-02 Gestión de ediciones y categorías (CU-06)."""
from django.contrib import messages
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import solo_administrador
from audit.services import registrar
from voting.models import Votacion
from voting.services import sincronizar_estados, votaciones_publicas

from .forms import CategoriaForm, EdicionForm, primer_error
from .models import Categoria, Edicion
from .utils import entero, mover_en_orden


# ====================================================================== públicas
def inicio(request):
    """P-01 · CU-03 paso 1-2 · RF-04: edición vigente y votaciones destacadas."""
    sincronizar_estados(request)
    edicion = Edicion.vigente()
    # Destacadas: primero las abiertas, máximo tres (igual que el prototipo).
    publicas = list(votaciones_publicas())
    destacadas = sorted(publicas, key=lambda v: 0 if v.estado == Votacion.ABIERTA else 1)[:3]
    return render(request, "catalog/p01_inicio.html", {"edicion": edicion, "destacadas": destacadas})


def categorias(request):
    """P-04 · CU-03 paso 2 · RF-04: categorías activas de la edición vigente."""
    sincronizar_estados(request)
    edicion = Edicion.vigente()
    lista = []
    if edicion:
        lista = (Categoria.objects.filter(edicion=edicion, estado=Categoria.ACTIVA)
                 .annotate(disponibles=Count("votaciones", filter=~Q(votaciones__estado=Votacion.BORRADOR))))
    return render(request, "catalog/p04_categorias.html", {"edicion": edicion, "categorias": lista})


# ====================================================================== administración
def _url_a02(edicion_id=None, **extra):
    url = reverse("catalog:admin_categorias")
    params = {k: v for k, v in {"edicion": edicion_id, **extra}.items() if v}
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return url


@solo_administrador
def admin_categorias(request):
    """A-02 · CU-06 · RF-11, RF-12: ediciones y sus categorías (filtros: edición · estado)."""
    ediciones = Edicion.objects.all()
    edicion = None
    if entero(request.GET.get("edicion")):
        edicion = ediciones.filter(pk=entero(request.GET["edicion"])).first()
    edicion = edicion or Edicion.vigente() or ediciones.first()

    filtro_estado = request.GET.get("estado", "")
    cats = Categoria.objects.none()
    if edicion:
        cats = edicion.categorias.annotate(
            abiertas=Count("votaciones", filter=Q(votaciones__estado=Votacion.ABIERTA)))
        if filtro_estado in (Categoria.ACTIVA, Categoria.INACTIVA):
            cats = cats.filter(estado=filtro_estado)

    editar = request.GET.get("editar", "")
    editar_edicion = request.GET.get("editar_edicion", "")
    return render(request, "catalog/a02_categorias.html", {
        "ediciones": ediciones,
        "edicion": edicion,
        "categorias": cats,
        "filtro_estado": filtro_estado,
        "editar": editar,
        "editar_edicion": editar_edicion,
        "form_edicion_nueva": EdicionForm(),
        "form_edicion": EdicionForm(instance=edicion) if edicion and editar_edicion == str(edicion.pk) else None,
    })


# ---------------------------------------------------------------- ediciones (RF-11)
@solo_administrador
@require_POST
def admin_edicion_crear(request):
    form = EdicionForm(request.POST)
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a02(request.POST.get("edicion_actual")))
    # CU-06 3b: una edición nueva parte de una configuración vacía e inactiva.
    edicion = form.save()
    registrar(request, f"Edición «{edicion}» creada")
    messages.success(request, "Edición creada. Actívala cuando esté lista.")
    return redirect(_url_a02(edicion.pk))


@solo_administrador
@require_POST
def admin_edicion_editar(request, pk):
    edicion = get_object_or_404(Edicion, pk=pk)
    form = EdicionForm(request.POST, instance=edicion)
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a02(pk, editar_edicion=pk))
    form.save()
    registrar(request, f"Edición «{edicion}» actualizada")
    messages.success(request, "Cambio guardado.")
    return redirect(_url_a02(pk))


@solo_administrador
@require_POST
def admin_edicion_estado(request, pk):
    """Activar o desactivar. Solo una edición está vigente a la vez (preliminar*)."""
    edicion = get_object_or_404(Edicion, pk=pk)
    if edicion.estado == Edicion.ACTIVA:
        if Votacion.objects.filter(categoria__edicion=edicion, estado=Votacion.ABIERTA).exists():
            messages.error(request, "No se puede desactivar una edición con votaciones abiertas.")
            return redirect(_url_a02(pk))
        edicion.estado = Edicion.INACTIVA
        edicion.save(update_fields=["estado"])
        registrar(request, f"Edición «{edicion}» desactivada")
        messages.success(request, "Edición desactivada.")
    else:
        otras_abiertas = Votacion.objects.filter(estado=Votacion.ABIERTA).exclude(categoria__edicion=edicion)
        if otras_abiertas.exists():
            messages.error(request, "Hay votaciones abiertas en la edición vigente. Ciérralas antes de cambiar de edición.")
            return redirect(_url_a02(pk))
        Edicion.objects.exclude(pk=pk).filter(estado=Edicion.ACTIVA).update(estado=Edicion.INACTIVA)
        edicion.estado = Edicion.ACTIVA
        edicion.save(update_fields=["estado"])
        registrar(request, f"Edición «{edicion}» activada como vigente")
        messages.success(request, "Edición activada. Es la que ve el público.")
    return redirect(_url_a02(pk))


# ---------------------------------------------------------------- categorías (RF-12)
@solo_administrador
@require_POST
def admin_categoria_crear(request):
    edicion = get_object_or_404(Edicion, pk=entero(request.POST.get("edicion")))
    form = CategoriaForm(request.POST, edicion=edicion)
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a02(edicion.pk))
    categoria = form.save(commit=False)
    categoria.edicion = edicion
    categoria.orden = (edicion.categorias.aggregate(m=Max("orden"))["m"] or 0) + 1
    categoria.save()
    registrar(request, f"Categoría «{categoria.nombre}» creada en {edicion}")
    messages.success(request, "Categoría creada.")
    return redirect(_url_a02(edicion.pk))


@solo_administrador
@require_POST
def admin_categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    anterior = categoria.nombre
    form = CategoriaForm(request.POST, instance=categoria)
    if not form.is_valid():
        messages.error(request, primer_error(form))
        return redirect(_url_a02(categoria.edicion_id, editar=pk))
    form.save()
    detalle = f"«{anterior}» → «{categoria.nombre}»" if anterior != categoria.nombre else ""
    registrar(request, f"Categoría «{categoria.nombre}» actualizada", detalle=detalle)
    messages.success(request, "Cambio guardado.")
    return redirect(_url_a02(categoria.edicion_id))


@solo_administrador
@require_POST
def admin_categoria_estado(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if categoria.activa:
        # CU-06 3a: no se desactiva una categoría con votaciones abiertas.
        if categoria.votaciones.filter(estado=Votacion.ABIERTA).exists():
            messages.error(request, "No se puede desactivar una categoría con votaciones abiertas.")
            return redirect(_url_a02(categoria.edicion_id))
        categoria.estado = Categoria.INACTIVA
    else:
        categoria.estado = Categoria.ACTIVA
    categoria.save(update_fields=["estado"])
    registrar(request, f"Categoría «{categoria.nombre}» {'activada' if categoria.activa else 'desactivada'}")
    messages.success(request, "Categoría activada." if categoria.activa else "Categoría desactivada.")
    return redirect(_url_a02(categoria.edicion_id))


@solo_administrador
@require_POST
def admin_categoria_mover(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if mover_en_orden(Categoria.objects.filter(edicion=categoria.edicion_id), categoria, request.POST.get("direccion")):
        registrar(request, f"Categoría «{categoria.nombre}» reordenada")
    return redirect(_url_a02(categoria.edicion_id))
