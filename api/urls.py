from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("categorias/", views.categorias, name="categorias"),               # GET /api/categorias/
    path("categorias/<int:pk>/", views.categoria, name="categoria"),        # GET /api/categorias/<id>/
]
