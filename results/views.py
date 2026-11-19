"""Resultados y panel.

Públicas (CU-05): listado «Resultados» (P-05) y resultados de una votación (P-09).
Administración (CU-09): A-01 Panel principal y A-05 Resultados + auditoría + exportación.
"""
import csv
from datetime import datetime, time

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import solo_administrador
from accounts.models import Usuario
from audit.models import RegistroAuditoria
from audit.services import registrar
from catalog.models import Edicion
from catalog.utils import entero
from voting.models import Votacion, Voto
from voting.services import sincronizar_estados, votaciones_publicas

from .excel import libro_de_resultados
from .services import calcular

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ====================================================================== públicas
def _votacion_con_resultados_visibles(request, pk):
    """Devuelve (votación, None) si el usuario puede ver sus resultados; si no, (None, redirección)."""
    v = get_object_or_404(Votacion.objects.select_related("categoria__edicion"), pk=pk)
    es_admin = request.user.is_authenticated and request.user.es_administrador
    publica = v.categoria.activa and v.categoria.edicion.estado == Edicion.ACTIVA
    if not es_admin and not (publica and v.resultados_publicos):
        # CU-05 2a: resultados no habilitados.
        messages.warning(request, "Los resultados aún no están disponibles.")
        destino = redirect("voting:detalle", pk) if publica and v.estado != Votacion.BORRADOR else redirect("catalog:inicio")
        return None, destino
    return v, None


def _respuesta_excel(contenido, nombre):
    respuesta = HttpResponse(contenido, content_type=TIPO_XLSX)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


def publicos(request):
    """P-05 en modo «Resultados» (barra inferior): votaciones con resultados publicados."""
    sincronizar_estados(request)
    votaciones = [v for v in votaciones_publicas() if v.resultados_publicos]
    return render(request, "voting/p05_votaciones.html", {
        "titulo": "Resultados",
        "subtitulo": "Votaciones con resultados disponibles",
        "votaciones": votaciones,
        "ya_votadas": set(),
        "vacio": "Aún no hay resultados publicados.",
        "volver": reverse("catalog:inicio"),
        "tab": "Resultados",
        "modo_resultados": True,
    })


def votacion(request, pk):
    """P-09 en modo resultados · CU-05 · RF-10 · RN-11."""
    sincronizar_estados(request)
    v, rechazo = _votacion_con_resultados_visibles(request, pk)
    if rechazo:
        return rechazo
    filas, total = calcular(v)
    return render(request, "results/p09_resultados.html", {"v": v, "filas": filas, "total": total, "corte": timezone.now()})


def descargar_votacion(request, pk):
    """Botón «Descargar resultados (Excel)» de una votación (P-09 y A-05).

    El público solo puede descargar lo que ya puede ver (RN-11); el administrador, cualquier votación.
    """
    sincronizar_estados(request)
    v, rechazo = _votacion_con_resultados_visibles(request, pk)
    if rechazo:
        return rechazo
    contenido = libro_de_resultados([v], titulo=f"Resultados · {v.titulo}")
    registrar(request, f"Descarga de resultados en Excel de «{v.titulo}»")
    return _respuesta_excel(contenido, f"resultados_votacion_{v.pk}.xlsx")


# ====================================================================== administración
@solo_administrador
def panel(request):
    """A-01 Panel principal: indicadores y accesos rápidos (CU-06 a CU-09)."""
    sincronizar_estados(request)
    return render(request, "results/a01_panel.html", {
        "edicion": Edicion.vigente(),
        "abiertas": Votacion.objects.filter(estado=Votacion.ABIERTA).count(),
        "votos": Voto.objects.filter(estado=Voto.REGISTRADO).count(),
        "usuarios": Usuario.objects.count(),
    })


def _filtrar_auditoria(params):
    """CU-09 paso 3: filtros por fecha, usuario y acción."""
    registros = RegistroAuditoria.objects.select_related("usuario")
    tz = timezone.get_current_timezone()
    try:
        if params.get("desde"):
            d = datetime.strptime(params["desde"], "%Y-%m-%d").date()
            registros = registros.filter(fecha_hora__gte=timezone.make_aware(datetime.combine(d, time.min), tz))
        if params.get("hasta"):
            d = datetime.strptime(params["hasta"], "%Y-%m-%d").date()
            registros = registros.filter(fecha_hora__lte=timezone.make_aware(datetime.combine(d, time.max), tz))
    except ValueError:
        pass
    if params.get("usuario"):
        u = params["usuario"].strip()
        if u.lower() == "sistema":
            registros = registros.filter(usuario__isnull=True)
        else:
            registros = registros.filter(usuario__correo__icontains=u)
    if params.get("accion"):
        registros = registros.filter(Q(accion__icontains=params["accion"].strip()) | Q(detalle__icontains=params["accion"].strip()))
    return registros


@solo_administrador
def admin_resultados(request):
    """A-05 · CU-09 · RF-15, RF-16, RF-17: resultados de cualquier votación y auditoría."""
    sincronizar_estados(request)
    votaciones = Votacion.objects.select_related("categoria")
    v = votaciones.filter(pk=entero(request.GET.get("votacion")) or 0).first() or votaciones.first()
    filas, total = calcular(v) if v else ([], 0)

    ver_auditoria = request.GET.get("auditoria") == "1"
    registros, total_registros = [], 0
    if ver_auditoria:
        qs = _filtrar_auditoria(request.GET)
        total_registros = qs.count()
        registros = qs[:200]
    return render(request, "results/a05_resultados.html", {
        "votaciones": votaciones, "v": v, "filas": filas, "total": total, "corte": timezone.now(),
        "ver_auditoria": ver_auditoria, "registros": registros, "total_registros": total_registros,
        "f": request.GET,
    })


@solo_administrador
def exportar(request, pk):
    """RF-17 (pendiente de validación*): exportación preliminar en CSV, abre en Excel."""
    v = get_object_or_404(Votacion, pk=pk)
    filas, total = calcular(v)
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="resultados_votacion_{v.pk}.csv"'
    respuesta.write("﻿")  # para que Excel muestre bien las tildes
    w = csv.writer(respuesta, delimiter=";")
    w.writerow(["Votación", v.titulo])
    w.writerow(["Estado", v.get_estado_display()])
    w.writerow(["Fecha de corte", timezone.localtime().strftime("%Y-%m-%d %H:%M")])
    w.writerow([])
    w.writerow(["Opción", "Activa", "Votos", "Porcentaje"])
    for f in filas:
        w.writerow([f["nombre"], "Sí" if f["activa"] else "No", f["votos"], f'{f["porcentaje"]} %'])
    w.writerow(["Total", "", total, ""])
    registrar(request, f"Exportación de resultados de «{v.titulo}»")
    return respuesta


@solo_administrador
def descargar_todos(request):
    """A-01 / A-05 · Botón «Descargar todos los resultados (Excel)»: todas las votaciones de una edición."""
    sincronizar_estados(request)
    ediciones = Edicion.objects.all()
    edicion = ediciones.filter(pk=entero(request.GET.get("edicion")) or 0).first() or Edicion.vigente()
    votaciones = (Votacion.objects.select_related("categoria__edicion")
                  .order_by("categoria__edicion__anio", "categoria__orden", "categoria__nombre", "pk"))
    if edicion:
        votaciones = votaciones.filter(categoria__edicion=edicion)
    titulo = f"Resultados de la edición {edicion.anio}" if edicion else "Resultados de todas las ediciones"
    contenido = libro_de_resultados(list(votaciones), titulo=titulo)
    registrar(request, "Descarga de todos los resultados en Excel", detalle=titulo)
    nombre = f"resultados_festival_{edicion.anio}.xlsx" if edicion else "resultados_festival.xlsx"
    return _respuesta_excel(contenido, nombre)
