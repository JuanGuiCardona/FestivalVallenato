"""Control de acceso por rol (RN-08: solo el administrador gestiona)."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

AVISO_ADMIN = "Esa pantalla es solo para administradores. Ingresa con una cuenta de administrador."


def ir_a_login(request, aviso, siguiente=None):
    """Lleva a P-03 mostrando un aviso y recordando a dónde volver (CU-02 5a)."""
    request.session["aviso_login"] = aviso
    url = reverse("accounts:login")
    if siguiente:
        url += "?" + urlencode({"next": siguiente})
    return redirect(url)


def solo_administrador(vista):
    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return ir_a_login(request, AVISO_ADMIN, request.get_full_path())
        if not request.user.es_administrador:
            messages.error(request, "Acceso solo para administradores.")
            return ir_a_login(request, AVISO_ADMIN)
        return vista(request, *args, **kwargs)

    return envuelta
