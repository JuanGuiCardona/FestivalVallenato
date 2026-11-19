"""Descarga de resultados en Excel (.xlsx) · RF-17.

Arma un libro con dos hojas a partir de los votos guardados en MySQL:
- «Resumen»: una fila por votación (categoría, estado, total de votos y opción líder).
- «Detalle»: una fila por opción (votos y porcentaje).
No incluye datos de los votantes: el voto es secreto.
"""
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .services import calcular

AZUL = "0B2E6B"
CREMA = "F3EEDF"
BORDE = Border(*(Side(style="thin", color="C9BFA8"),) * 4)


def _encabezado(hoja, fila, titulos):
    for col, titulo in enumerate(titulos, start=1):
        celda = hoja.cell(row=fila, column=col, value=titulo)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor=AZUL)
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        celda.border = BORDE


def _titulo(hoja, texto, subtitulo):
    hoja["A1"] = texto
    hoja["A1"].font = Font(bold=True, size=14, color=AZUL)
    hoja["A2"] = subtitulo
    hoja["A2"].font = Font(italic=True, color="5A5F6B")


def _ajustar(hoja, anchos, primera_fila):
    for i, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    for fila in hoja.iter_rows(min_row=primera_fila + 1, max_row=hoja.max_row):
        for celda in fila:
            celda.border = BORDE
            celda.alignment = Alignment(vertical="top", wrap_text=True)
    hoja.freeze_panes = hoja.cell(row=primera_fila + 1, column=1)


def libro_de_resultados(votaciones, titulo="Resultados de las votaciones"):
    """Devuelve el contenido del archivo .xlsx (bytes) con los resultados de las votaciones dadas."""
    corte = timezone.localtime().strftime("%Y-%m-%d %H:%M")
    subtitulo = f"Festival de la Leyenda Vallenata · corte {corte} (hora de Colombia) · el voto es secreto"
    libro = Workbook()

    resumen = libro.active
    resumen.title = "Resumen"
    _titulo(resumen, titulo, subtitulo)
    _encabezado(resumen, 4, ["Edición", "Categoría", "Votación", "Estado", "Total de votos",
                             "Opción líder", "Votos de la líder", "Porcentaje de la líder"])

    detalle = libro.create_sheet("Detalle")
    _titulo(detalle, f"{titulo} · detalle por opción", subtitulo)
    _encabezado(detalle, 4, ["Edición", "Categoría", "Votación", "Estado", "Opción", "Opción activa",
                             "Votos", "Porcentaje"])

    for v in votaciones:
        filas, total = calcular(v)
        edicion = v.categoria.edicion.anio
        lideres = [f for f in filas if f["lider"]]
        resumen.append([
            edicion, v.categoria.nombre, v.titulo, v.get_estado_display(), total,
            " / ".join(f["nombre"] for f in lideres) if lideres else "Sin votos",
            lideres[0]["votos"] if lideres else 0,
            (lideres[0]["porcentaje"] / 100) if lideres else 0,
        ])
        for f in filas:
            detalle.append([edicion, v.categoria.nombre, v.titulo, v.get_estado_display(), f["nombre"],
                            "Sí" if f["activa"] else "No", f["votos"], f["porcentaje"] / 100])
        if not filas:
            detalle.append([edicion, v.categoria.nombre, v.titulo, v.get_estado_display(), "Sin opciones", "", 0, 0])

    for hoja, col_pct in ((resumen, "H"), (detalle, "H")):
        for celda in hoja[col_pct][4:]:
            celda.number_format = "0%"
    _ajustar(resumen, [9, 22, 34, 14, 14, 26, 14, 14], 4)
    _ajustar(detalle, [9, 22, 34, 14, 26, 12, 10, 12], 4)
    if resumen.max_row > 4:
        resumen.auto_filter.ref = f"A4:H{resumen.max_row}"
        detalle.auto_filter.ref = f"A4:H{detalle.max_row}"

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()
