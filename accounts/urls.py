from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("registro/", views.registro, name="registro"),                 # P-02
    path("ingresar/", views.iniciar_sesion, name="login"),              # P-03
    path("salir/", views.cerrar_sesion, name="logout"),
    path("recuperar-clave/", views.recuperar_clave, name="recuperar"),  # RF-03 (pendiente*)
]
