"""Función única para dejar rastro de las acciones críticas (RN-13)."""
from .models import RegistroAuditoria


def ip_cliente(request):
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = reenviada.split(",")[0].strip() if reenviada else request.META.get("REMOTE_ADDR")
    return ip or None


def registrar(request, accion, detalle="", usuario=None):
    """Guarda quién hizo qué y cuándo (RNF-14).

    Por secreto del voto, al auditar un voto NUNCA se incluye la opción elegida.
    """
    if usuario is None and request is not None and request.user.is_authenticated:
        usuario = request.user
    return RegistroAuditoria.objects.create(
        usuario=usuario,
        accion=accion[:255],
        detalle=detalle,
        ip=ip_cliente(request),
    )
