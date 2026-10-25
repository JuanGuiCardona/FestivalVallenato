from django.urls import path

from . import views

app_name = "results"

urlpatterns = [
    path("resultados/", views.publicos, name="publicos"),                          # P-05 (modo resultados)
    path("resultados/<int:pk>/", views.votacion, name="votacion"),                 # P-09 (modo resultados)
    path("panel/", views.panel, name="panel"),                                      # A-01
    path("panel/resultados/", views.admin_resultados, name="admin_resultados"),    # A-05
    path("panel/resultados/<int:pk>/exportar/", views.exportar, name="exportar"),  # RF-17 (preliminar*)
]
