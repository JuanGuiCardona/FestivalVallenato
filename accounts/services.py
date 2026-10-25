"""Control de intentos de inicio de sesión (CU-02 4b · RNF-04, preliminar*)."""
from django.conf import settings
from django.core.cache import cache

from audit.services import ip_cliente


def _llave(request, correo):
    return f"login:{ip_cliente(request)}:{correo}"


def esta_bloqueado(request, correo):
    return cache.get(_llave(request, correo), 0) >= settings.LOGIN_MAX_INTENTOS


def registrar_fallo(request, correo):
    """Suma un intento fallido. Devuelve True si con este intento quedó bloqueado."""
    llave = _llave(request, correo)
    intentos = cache.get(llave, 0) + 1
    cache.set(llave, intentos, settings.LOGIN_BLOQUEO_SEGUNDOS)
    return intentos >= settings.LOGIN_MAX_INTENTOS


def limpiar(request, correo):
    cache.delete(_llave(request, correo))


def minutos_bloqueo():
    return max(1, settings.LOGIN_BLOQUEO_SEGUNDOS // 60)
