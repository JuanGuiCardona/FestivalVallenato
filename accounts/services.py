"""Control de intentos de inicio de sesión (CU-02 4b · RNF-04, preliminar*)."""
from django.core.cache import cache

from audit.services import ip_cliente


def _config():
    # La configuración se edita desde la interfaz (A-06); si no se ha guardado, usa el .env.
    from voting.models import Configuracion
    return Configuracion.actual()


def _llave(request, correo):
    return f"login:{ip_cliente(request)}:{correo}"


def esta_bloqueado(request, correo):
    return cache.get(_llave(request, correo), 0) >= _config().max_intentos_login


def registrar_fallo(request, correo):
    """Suma un intento fallido. Devuelve True si con este intento quedó bloqueado."""
    config = _config()
    llave = _llave(request, correo)
    intentos = cache.get(llave, 0) + 1
    cache.set(llave, intentos, config.minutos_bloqueo * 60)
    return intentos >= config.max_intentos_login


def limpiar(request, correo):
    cache.delete(_llave(request, correo))


def minutos_bloqueo():
    return _config().minutos_bloqueo
