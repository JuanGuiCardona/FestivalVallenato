"""Pruebas de CU-01 Registrarse y CU-02 Iniciar sesión.

Ejecutar: python manage.py test accounts
"""
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from audit.models import RegistroAuditoria
from plataforma_festival.fabrica_pruebas import CLAVE, crear_base, crear_usuario

from .models import Rol, Usuario


def datos_registro(**cambios):
    datos = {"nombre": "Ana Pérez", "correo": "ana@correo.co", "clave": "Vallenato#2027",
             "clave2": "Vallenato#2027", "ciudad": "Valledupar", "acepta": "on"}
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


class CU01RegistroTests(TestCase):
    def test_registro_exitoso_crea_votante_con_hash_y_aceptacion(self):
        r = self.client.post("/registro/", datos_registro())
        self.assertRedirects(r, "/ingresar/", fetch_redirect_response=False)
        u = Usuario.objects.get(correo="ana@correo.co")
        self.assertEqual(u.rol.nombre, Rol.VOTANTE)                  # CU-01 paso 5
        self.assertNotEqual(u.password, "Vallenato#2027")             # RNF-02
        self.assertTrue(u.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(u.acepta_datos)                                # RN-12
        self.assertIsNotNone(u.fecha_aceptacion)
        self.assertTrue(RegistroAuditoria.objects.filter(accion__startswith="Cuenta creada").exists())
        r = self.client.get("/ingresar/")
        self.assertContains(r, "Cuenta creada. Inicia sesión para votar.")
        self.assertContains(r, 'value="ana@correo.co"')

    def test_3a_sin_aceptar_datos_no_crea_cuenta(self):
        r = self.client.post("/registro/", datos_registro(acepta=None))
        self.assertContains(r, "Debes aceptar el tratamiento de datos personales")
        self.assertFalse(Usuario.objects.exists())

    def test_4a_correo_duplicado_sin_importar_mayusculas(self):
        crear_usuario("ana@correo.co")
        r = self.client.post("/registro/", datos_registro(correo="ANA@Correo.co"))
        self.assertContains(r, "Ese correo ya está registrado")
        self.assertEqual(Usuario.objects.count(), 1)

    def test_4b_datos_invalidos(self):
        casos = [
            (datos_registro(nombre="A"), "Escribe tu nombre completo."),
            (datos_registro(correo="ana@"), "Escribe un correo válido"),
            (datos_registro(clave="corta", clave2="corta"), "al menos 8 caracteres"),
            (datos_registro(clave2="Otra#2027x"), "Las contraseñas no coinciden."),
            (datos_registro(clave="12345678", clave2="12345678"), "contraseña"),  # validadores de Django
        ]
        for datos, mensaje in casos:
            with self.subTest(mensaje=mensaje):
                self.assertContains(self.client.post("/registro/", datos), mensaje)
        self.assertFalse(Usuario.objects.exists())


class CU02InicioSesionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.votante = crear_usuario("votante@prueba.co")
        self.admin = crear_usuario("admin@prueba.co", admin=True)

    def entrar(self, correo, clave=CLAVE, **extra):
        return self.client.post("/ingresar/", {"correo": correo, "clave": clave, **extra})

    def test_paso5_redirige_segun_rol(self):
        self.assertRedirects(self.entrar("votante@prueba.co"), "/categorias/")
        self.client.post("/salir/")
        self.assertRedirects(self.entrar("ADMIN@prueba.co"), "/panel/")
        self.assertTrue(RegistroAuditoria.objects.filter(accion="Inicio de sesión de administrador").exists())

    def test_5a_vuelve_a_la_votacion_de_origen(self):
        _, _, votacion = crear_base()
        destino = f"/votaciones/{votacion.pk}/opciones/"
        r = self.entrar("votante@prueba.co", next=destino)
        self.assertRedirects(r, destino)

    def test_no_redirige_a_sitios_externos(self):
        r = self.entrar("votante@prueba.co", next="https://sitio-malicioso.com/")
        self.assertRedirects(r, "/categorias/")

    def test_4a_mensaje_generico(self):
        for correo in ("votante@prueba.co", "noexiste@prueba.co"):
            r = self.entrar(correo, "incorrecta")
            self.assertContains(r, "Credenciales inválidas")

    @override_settings(LOGIN_MAX_INTENTOS=3, LOGIN_BLOQUEO_SEGUNDOS=120)
    def test_4b_bloqueo_temporal_por_intentos(self):
        for _ in range(2):
            self.assertContains(self.entrar("votante@prueba.co", "mala"), "Credenciales inválidas")
        self.assertContains(self.entrar("votante@prueba.co", "mala"), "Bloqueo temporal de 2 minutos")
        # Ni con la clave correcta entra mientras dure el bloqueo.
        self.assertContains(self.entrar("votante@prueba.co"), "Demasiados intentos fallidos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_4c_cuenta_inactiva_o_bloqueada(self):
        self.votante.estado = Usuario.BLOQUEADO
        self.votante.save()
        r = self.entrar("votante@prueba.co")
        self.assertContains(r, "Tu cuenta está inactiva o bloqueada")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cerrar_sesion_solo_por_post(self):
        self.entrar("votante@prueba.co")
        self.assertEqual(self.client.get("/salir/").status_code, 405)
        self.client.post("/salir/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_rf03_recuperar_clave_pendiente(self):
        r = self.client.get("/recuperar-clave/", follow=True)
        self.assertContains(r, "pendiente de validación con el cliente")

    def test_rnf03_csrf_obligatorio(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post("/ingresar/", {"correo": "votante@prueba.co", "clave": CLAVE})
        self.assertEqual(r.status_code, 403)
