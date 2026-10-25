from django.contrib import admin

from .models import Rol, Usuario


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("id_rol", "nombre")


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("correo", "nombre", "rol", "estado", "acepta_datos", "fecha_registro")
    list_filter = ("rol", "estado", "acepta_datos")
    search_fields = ("correo", "nombre")
    fields = ("correo", "nombre", "rol", "estado", "ciudad", "acepta_datos", "fecha_aceptacion",
              "fecha_registro", "last_login", "is_superuser")
    readonly_fields = ("acepta_datos", "fecha_aceptacion", "fecha_registro", "last_login")

    def has_delete_permission(self, request, obj=None):
        # Un usuario con votos no se borra (se conserva el historial): se cambia su estado.
        return False
