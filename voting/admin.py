from django.contrib import admin
from django.db.models import Count

from .models import Opcion, Votacion, Voto


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 0
    fields = ("nombre", "descripcion", "orden", "estado")

    def has_delete_permission(self, request, obj=None):
        return False  # RN-10


@admin.register(Votacion)
class VotacionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "estado", "fecha_apertura", "fecha_cierre",
                    "max_votos_por_votante", "periodicidad_voto", "resultados_visibles", "total_votos")
    list_filter = ("estado", "categoria__edicion", "categoria", "resultados_visibles")
    search_fields = ("titulo",)
    inlines = [OpcionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total=Count("votos"))

    @admin.display(description="Votos", ordering="_total")
    def total_votos(self, obj):
        return obj._total

    def has_delete_permission(self, request, obj=None):
        return False  # RN-10


@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    """Solo lectura: ningún voto se crea, edita ni borra a mano (RN-07, R-09)."""
    list_display = ("codigo", "votacion", "fecha_hora", "estado")
    list_filter = ("votacion", "estado")
    search_fields = ("codigo",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
