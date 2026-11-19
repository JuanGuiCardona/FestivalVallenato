"""Función única para dejar rastro de las acciones críticas (RN-13)."""
from django.conf import settings

from .models import RegistroAuditoria


def ip_cliente(request):
    """IP del cliente para la auditoría y el bloqueo por intentos.

    X-Forwarded-For solo se usa detrás de un proxy de confianza (DJANGO_DETRAS_DE_PROXY=1),
    y entonces se toma el último valor, que es el que agrega ese proxy. Así nadie puede
    cambiar su IP escribiendo el encabezado a mano para saltarse el bloqueo.
    """
    if request is None:
        return None
    ip = request.META.get("REMOTE_ADDR")
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviada and settings.DETRAS_DE_PROXY:
        ip = reenviada.split(",")[-1].strip()
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
