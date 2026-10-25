from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.inicio, name="inicio"),                       # P-01
    path("categorias/", views.categorias, name="categorias"),    # P-04
    # A-02 · Gestión de ediciones y categorías (solo administrador)
    path("panel/categorias/", views.admin_categorias, name="admin_categorias"),
    path("panel/categorias/nueva/", views.admin_categoria_crear, name="admin_categoria_crear"),
    path("panel/categorias/<int:pk>/editar/", views.admin_categoria_editar, name="admin_categoria_editar"),
    path("panel/categorias/<int:pk>/estado/", views.admin_categoria_estado, name="admin_categoria_estado"),
    path("panel/categorias/<int:pk>/mover/", views.admin_categoria_mover, name="admin_categoria_mover"),
    path("panel/ediciones/nueva/", views.admin_edicion_crear, name="admin_edicion_crear"),
    path("panel/ediciones/<int:pk>/editar/", views.admin_edicion_editar, name="admin_edicion_editar"),
    path("panel/ediciones/<int:pk>/estado/", views.admin_edicion_estado, name="admin_edicion_estado"),
]
