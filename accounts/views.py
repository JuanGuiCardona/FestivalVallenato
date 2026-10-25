"""Pantallas P-02 Registro y P-03 Inicio de sesión (CU-01, CU-02)."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from audit.services import registrar

from . import services
from .forms import LoginForm, RegistroForm
from .models import Usuario


def _siguiente(request):
    """Dirección a la que se vuelve tras iniciar sesión (CU-02 5a), solo si es de este sitio."""
    url = request.POST.get("next") or request.GET.get("next") or ""
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return ""


def registro(request):
    """P-02 · CU-01 Registrarse (RF-01, RN-12, RN-14)."""
    siguiente = _siguiente(request)
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        usuario = Usuario.objects.create_user(
            correo=d["correo"], password=d["clave"], nombre=d["nombre"], ciudad=d["ciudad"],
            acepta_datos=True, fecha_aceptacion=timezone.now(),
        )
        registrar(request, "Cuenta creada con aceptación de datos", detalle=usuario.correo, usuario=usuario)
        messages.success(request, "Cuenta creada.")
        # CU-01 paso 6: confirma y dirige al inicio de sesión.
        request.session["aviso_login"] = "Cuenta creada. Inicia sesión para votar."
        request.session["correo_registrado"] = usuario.correo
        url = reverse("accounts:login")
        return redirect(url + ("?" + urlencode({"next": siguiente}) if siguiente else ""))

    return render(request, "accounts/p02_registro.html", {
        "form": form,
        "error": form.primer_error if request.method == "POST" else "",
        "siguiente": siguiente,
    })


def iniciar_sesion(request):
    """P-03 · CU-02 Iniciar sesión (RF-02, RNF-04)."""
    siguiente = _siguiente(request)
    aviso = request.session.pop("aviso_login", "")
    form = LoginForm(request.POST or None, initial={"correo": request.session.pop("correo_registrado", "")})
    error = ""

    if request.method == "POST" and form.is_valid():
        correo, clave = form.cleaned_data["correo"], form.cleaned_data["clave"]
        if services.esta_bloqueado(request, correo):
            error = f"Demasiados intentos fallidos. Espera {services.minutos_bloqueo()} minutos e inténtalo de nuevo."
        else:
            usuario = authenticate(request, username=correo, password=clave)
            if usuario is None:
                existente = Usuario.objects.filter(correo__iexact=correo).first()
                if existente and not existente.is_active and existente.check_password(clave):
                    # CU-02 4c: cuenta bloqueada o inactiva.
                    error = "Tu cuenta está inactiva o bloqueada. Comunícate con la organización del Festival."
                else:
                    bloqueado = services.registrar_fallo(request, correo)
                    registrar(request, "Intento fallido de inicio de sesión", detalle=correo or "sin correo")
                    error = (f"Demasiados intentos fallidos. Bloqueo temporal de {services.minutos_bloqueo()} minutos."
                             if bloqueado else
                             "Credenciales inválidas. Revisa tu correo y contraseña e inténtalo de nuevo.")
            else:
                services.limpiar(request, correo)
                login(request, usuario)
                registrar(request, "Inicio de sesión de administrador" if usuario.es_administrador else "Inicio de sesión")
                messages.success(request, "Sesión iniciada.")
                # CU-02 paso 5: redirige según el rol.
                if usuario.es_administrador:
                    return redirect("results:panel")
                return redirect(siguiente or "catalog:categorias")

    demo = settings.DEBUG and Usuario.objects.filter(correo="votante@demo.co").exists()
    return render(request, "accounts/p03_login.html", {
        "form": form, "error": error, "aviso": aviso, "siguiente": siguiente, "mostrar_demo": demo,
    })


@require_POST
def cerrar_sesion(request):
    if request.user.is_authenticated:
        registrar(request, "Cierre de sesión")
    logout(request)
    messages.success(request, "Sesión cerrada.")
    return redirect("catalog:inicio")


def recuperar_clave(request):
    """RF-03: pendiente de validación con el cliente (requiere servicio de correo)."""
    messages.warning(request, "Recuperar la contraseña está pendiente de validación con el cliente*.")
    return redirect("accounts:login")
