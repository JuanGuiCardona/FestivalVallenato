"""Datos mínimos que comparten las pruebas automáticas de las cinco apps."""
from datetime import timedelta

from django.utils import timezone

from accounts.models import Rol, Usuario
from catalog.models import Categoria, Edicion
from voting.models import Opcion, Votacion

CLAVE = "Acordeon#2027"


def crear_usuario(correo="votante@prueba.co", admin=False, **extra):
    u = Usuario(correo=correo, nombre=extra.pop("nombre", "Persona de Prueba"),
                rol=Rol.obtener(Rol.ADMINISTRADOR if admin else Rol.VOTANTE),
                acepta_datos=True, fecha_aceptacion=timezone.now(), **extra)
    u.set_password(CLAVE)
    u.save()
    return u


def crear_base():
    """Edición vigente 2027 › Música › votación abierta con 3 opciones."""
    edicion = Edicion.objects.create(nombre="60° Festival", anio=2027, estado=Edicion.ACTIVA)
    categoria = Categoria.objects.create(edicion=edicion, nombre="Música", orden=0)
    votacion = crear_votacion(categoria)
    return edicion, categoria, votacion


def crear_votacion(categoria, titulo="Canción favorita", estado=Votacion.ABIERTA, opciones=3, **extra):
    ahora = timezone.now()
    extra.setdefault("fecha_apertura", ahora - timedelta(hours=1) if estado == Votacion.ABIERTA else None)
    extra.setdefault("fecha_cierre", ahora + timedelta(days=5))
    votacion = Votacion.objects.create(categoria=categoria, titulo=titulo, estado=estado, **extra)
    for i in range(opciones):
        Opcion.objects.create(votacion=votacion, nombre=f"Opción {chr(65 + i)}", descripcion="Prueba", orden=i)
    return votacion
