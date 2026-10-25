from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """Solo lectura (RNF-14)."""
    list_display = ("fecha_hora", "autor", "accion", "ip")
    list_filter = ("fecha_hora",)
    search_fields = ("accion", "detalle", "usuario__correo")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
