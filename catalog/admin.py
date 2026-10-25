from django.contrib import admin

from .models import Categoria, Edicion


@admin.register(Edicion)
class EdicionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "anio", "fecha_inicio", "fecha_fin", "estado")
    list_filter = ("estado",)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edicion", "orden", "estado")
    list_filter = ("edicion", "estado")
    search_fields = ("nombre",)

    def has_delete_permission(self, request, obj=None):
        return False  # RN-10: se desactivan, no se borran
