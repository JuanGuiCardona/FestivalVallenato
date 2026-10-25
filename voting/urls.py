from django.urls import path

from . import views

app_name = "voting"

urlpatterns = [
    path("categorias/<int:pk>/", views.por_categoria, name="por_categoria"),        # P-05
    path("votaciones/<int:pk>/", views.detalle, name="detalle"),                     # P-06
    path("votaciones/<int:pk>/opciones/", views.opciones, name="opciones"),          # P-07
    path("votaciones/<int:pk>/confirmar/", views.confirmar, name="confirmar"),       # P-08
    path("votaciones/<int:pk>/ya-votaste/", views.ya_voto, name="ya_voto"),          # P-09
    path("comprobante/<str:codigo>/", views.comprobante, name="comprobante"),        # P-09
    # A-03 · Gestión de votaciones
    path("panel/votaciones/", views.admin_votaciones, name="admin_votaciones"),
    path("panel/votaciones/<int:pk>/configurar/", views.admin_votacion_configurar, name="admin_votacion_configurar"),
    path("panel/votaciones/<int:pk>/estado/", views.admin_votacion_estado, name="admin_votacion_estado"),
    # A-04 · Gestión de opciones
    path("panel/opciones/", views.admin_opciones, name="admin_opciones"),
    path("panel/opciones/nueva/", views.admin_opcion_crear, name="admin_opcion_crear"),
    path("panel/opciones/<int:pk>/editar/", views.admin_opcion_editar, name="admin_opcion_editar"),
    path("panel/opciones/<int:pk>/estado/", views.admin_opcion_estado, name="admin_opcion_estado"),
    path("panel/opciones/<int:pk>/mover/", views.admin_opcion_mover, name="admin_opcion_mover"),
]
