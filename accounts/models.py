"""Entidades Rol y Usuario del modelo conceptual (sección 11 del documento).

- Rol 1:N Usuario.
- Usuario guarda la aceptación del tratamiento de datos y su fecha (11.2, RN-12).
- La contraseña se guarda con hash (RNF-02); nunca en texto plano.
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class Rol(models.Model):
    VOTANTE = "Votante"
    ADMINISTRADOR = "Administrador"

    id_rol = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "rol"
        verbose_name = "rol"
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre

    @classmethod
    def obtener(cls, nombre):
        rol, _ = cls.objects.get_or_create(nombre=nombre)
        return rol


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, correo, password, rol_nombre, **extra):
        if not correo:
            raise ValueError("El correo es obligatorio.")
        correo = self.normalize_email(correo).lower()
        extra.setdefault("rol", Rol.obtener(rol_nombre))
        usuario = self.model(correo=correo, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault("is_superuser", False)
        return self._crear(correo, password, Rol.VOTANTE, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra["is_superuser"] = True
        extra.setdefault("acepta_datos", True)
        extra.setdefault("fecha_aceptacion", timezone.now())
        return self._crear(correo, password, Rol.ADMINISTRADOR, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    ACTIVO, INACTIVO, BLOQUEADO = "activo", "inactivo", "bloqueado"
    ESTADOS = [(ACTIVO, "Activo"), (INACTIVO, "Inactivo"), (BLOQUEADO, "Bloqueado")]

    id_usuario = models.BigAutoField(primary_key=True)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column="id_rol", related_name="usuarios")
    nombre = models.CharField(max_length=150)
    correo = models.EmailField(max_length=254, unique=True)  # RN-14: un correo por cuenta
    # "contraseña" del diagrama = campo password heredado (guarda el hash).
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ACTIVO)
    # RN-12 / Ley 1581 de 2012: autorización previa del titular.
    acepta_datos = models.BooleanField(default=False)
    fecha_aceptacion = models.DateTimeField(null=True, blank=True)
    # Dato adicional del prototipo, sujeto a validación con el cliente*.
    ciudad = models.CharField(max_length=120, blank=True)
    fecha_registro = models.DateTimeField(default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.correo

    # Django usa is_active para permitir o no el inicio de sesión (CU-02 4c).
    @property
    def is_active(self):
        return self.estado == self.ACTIVO

    # El rol Administrador da acceso al panel (RN-08) y al /admin/ de Django.
    @property
    def es_administrador(self):
        return self.rol_id is not None and self.rol.nombre == Rol.ADMINISTRADOR

    @property
    def is_staff(self):
        return self.es_administrador

    def get_full_name(self):
        return self.nombre

    def get_short_name(self):
        return self.nombre.split(" ")[0] if self.nombre else self.correo
