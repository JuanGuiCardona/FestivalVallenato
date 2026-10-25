"""Direcciones del sitio. Cada app aporta las suyas (organización de la sección 15.4)."""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Votaciones · Festival Vallenato 2027"
admin.site.site_title = "Administración técnica"
admin.site.index_title = "Panel técnico de Django"

urlpatterns = [
    path("admin/", admin.site.urls),          # panel técnico de Django
    path("", include("catalog.urls")),        # P-01, P-04, A-02
    path("", include("accounts.urls")),       # P-02, P-03
    path("", include("voting.urls")),         # P-05 a P-09, A-03, A-04
    path("", include("results.urls")),        # resultados, A-01, A-05
]
