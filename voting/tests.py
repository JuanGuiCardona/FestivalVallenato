"""Pruebas de CU-04 Emitir voto, CU-07 Gestionar votaciones y CU-08 Gestionar opciones.

Ejecutar: python manage.py test voting
"""
import threading
from datetime import date, timedelta
from unittest import mock, skipIf

from django.contrib.admin.sites import site
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from audit.models import RegistroAuditoria
from plataforma_festival.fabrica_pruebas import CLAVE, crear_base, crear_usuario, crear_votacion

from . import services
from catalog.models import Categoria

from .models import Configuracion, Opcion, Votacion, Voto


class BaseVoto(TestCase):
    def setUp(self):
        cache.clear()
        self.edicion, self.categoria, self.votacion = crear_base()
        self.votante = crear_usuario("votante@prueba.co")
        self.opcion = self.votacion.opciones.first()

    def entrar(self, correo="votante@prueba.co"):
        self.client.post("/ingresar/", {"correo": correo, "clave": CLAVE})

    def votar(self, votacion=None, opcion=None):
        votacion, opcion = votacion or self.votacion, opcion or self.opcion
        self.client.post(f"/votaciones/{votacion.pk}/opciones/", {"opcion": opcion.pk})
        return self.client.post(f"/votaciones/{votacion.pk}/confirmar/")


class CU04EmitirVotoTests(BaseVoto):
    def test_flujo_principal_registra_voto_con_comprobante_y_auditoria(self):
        self.entrar()
        r = self.client.get(f"/votaciones/{self.votacion.pk}/opciones/")
        self.assertContains(r, "Opción A")
        r = self.client.post(f"/votaciones/{self.votacion.pk}/opciones/", {"opcion": self.opcion.pk})
        self.assertRedirects(r, f"/votaciones/{self.votacion.pk}/confirmar/")
        self.assertContains(self.client.get(r.url), "Opción elegida: <b>Opción A</b>")   # paso 5
        r = self.client.post(f"/votaciones/{self.votacion.pk}/confirmar/")                # paso 6-8
        voto = Voto.objects.get()
        self.assertRedirects(r, f"/comprobante/{voto.codigo}/")
        self.assertContains(self.client.get(r.url), voto.codigo)                           # paso 9 (RF-09)
        self.assertEqual((voto.usuario, voto.opcion, voto.periodo), (self.votante, self.opcion, "UNICA"))
        registro = RegistroAuditoria.objects.get(accion="Voto registrado")               # RN-13
        self.assertNotIn("Opción A", registro.detalle)                                    # secreto del voto

    def test_2a_sin_sesion_pasa_por_login_y_regresa(self):
        url = f"/votaciones/{self.votacion.pk}/opciones/"
        r = self.client.get(url)
        self.assertRedirects(r, "/ingresar/?next=%2Fvotaciones%2F" + str(self.votacion.pk) + "%2Fopciones%2F",
                             fetch_redirect_response=False)
        self.assertContains(self.client.get(r.url), "Inicia sesión o regístrate para votar")
        r = self.client.post("/ingresar/", {"correo": "votante@prueba.co", "clave": CLAVE, "next": url})
        self.assertRedirects(r, url)

    def test_2b_votacion_no_abierta(self):
        self.entrar()
        for estado in (Votacion.PROXIMA, Votacion.CERRADA):
            with self.subTest(estado=estado):
                # «Próxima» con apertura futura; si la fecha ya pasó se abriría sola (RN-04).
                Votacion.objects.filter(pk=self.votacion.pk).update(
                    estado=estado, fecha_apertura=timezone.now() + timedelta(days=1) if estado == Votacion.PROXIMA else None)
                r = self.client.get(f"/votaciones/{self.votacion.pk}/opciones/")
                self.assertRedirects(r, f"/votaciones/{self.votacion.pk}/")
        self.assertFalse(Voto.objects.exists())

    def test_4a_no_elige_opcion(self):
        self.entrar()
        r = self.client.post(f"/votaciones/{self.votacion.pk}/opciones/", {})
        self.assertContains(r, "Selecciona una opción para continuar.")

    def test_6a_cancelar_no_registra(self):
        self.entrar()
        self.client.post(f"/votaciones/{self.votacion.pk}/opciones/", {"opcion": self.opcion.pk})
        self.client.get(f"/votaciones/{self.votacion.pk}/")  # «Volver»/«Cancelar» son solo enlaces
        self.assertFalse(Voto.objects.exists())

    def test_7a_ya_voto_no_registra_otro(self):
        self.entrar()
        self.votar()
        r = self.client.get(f"/votaciones/{self.votacion.pk}/opciones/")
        self.assertRedirects(r, f"/votaciones/{self.votacion.pk}/ya-votaste/")
        self.client.session[f"seleccion_{self.votacion.pk}"] = self.opcion.pk
        r = self.votar()
        self.assertEqual(Voto.objects.count(), 1)
        self.assertContains(self.client.get(f"/votaciones/{self.votacion.pk}/ya-votaste/"), "No se registró un voto nuevo.")

    def test_7b_la_base_de_datos_rechaza_duplicados(self):
        Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=self.opcion, periodo="UNICA", numero=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=self.opcion, periodo="UNICA", numero=1)

    def test_rn04_la_votacion_se_cierra_sola_al_pasar_la_fecha(self):
        Votacion.objects.filter(pk=self.votacion.pk).update(fecha_cierre=timezone.now() - timedelta(seconds=1))
        self.entrar()
        self.client.post(f"/votaciones/{self.votacion.pk}/opciones/", {"opcion": self.opcion.pk})
        self.votacion.refresh_from_db()
        self.assertEqual(self.votacion.estado, Votacion.CERRADA)
        self.assertFalse(Voto.objects.exists())
        self.assertTrue(RegistroAuditoria.objects.filter(accion__startswith="Cierre programado", usuario=None).exists())

    def test_rn06_periodicidad_diaria(self):
        self.votacion.periodicidad_voto = Votacion.DIARIA
        self.votacion.save()
        self.entrar()
        with mock.patch("django.utils.timezone.localdate", return_value=date(2027, 4, 28)):
            self.votar()
            self.votar()
            self.assertEqual(Voto.objects.count(), 1)
        with mock.patch("django.utils.timezone.localdate", return_value=date(2027, 4, 29)):
            self.votar()
        self.assertEqual(list(Voto.objects.order_by("periodo").values_list("periodo", flat=True)), ["2027-04-28", "2027-04-29"])

    def test_rn06_maximo_de_votos_por_votante(self):
        self.votacion.max_votos_por_votante = 2
        self.votacion.save()
        self.entrar()
        for _ in range(3):
            self.votar()
        self.assertEqual(Voto.objects.count(), 2)
        self.assertEqual(sorted(Voto.objects.values_list("numero", flat=True)), [1, 2])

    def test_11_2_la_opcion_debe_ser_de_la_misma_votacion(self):
        otra = crear_votacion(self.categoria, titulo="Otra")
        with self.assertRaises(ValidationError):
            Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=otra.opciones.first(), periodo="UNICA")
        request = RequestFactory().post("/")
        request.user = self.votante
        with self.assertRaises(services.ReglaVoto):
            services.emitir_voto(request, self.votacion.pk, otra.opciones.first().pk)

    def test_opcion_inactiva_no_se_puede_votar(self):
        Opcion.objects.filter(pk=self.opcion.pk).update(estado=Opcion.INACTIVA)
        self.entrar()
        r = self.client.post(f"/votaciones/{self.votacion.pk}/opciones/", {"opcion": self.opcion.pk})
        self.assertContains(r, "Selecciona una opción para continuar.")

    def test_el_administrador_no_vota(self):
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")
        r = self.client.get(f"/votaciones/{self.votacion.pk}/opciones/")
        self.assertRedirects(r, f"/votaciones/{self.votacion.pk}/")
        self.assertFalse(Voto.objects.exists())

    @override_settings(VOTOS_MAX_POR_MINUTO=2)
    def test_rnf04_limite_de_solicitudes(self):
        request = RequestFactory().post("/")
        request.user = self.votante
        self.votacion.max_votos_por_votante = 10
        self.votacion.save()
        services.emitir_voto(request, self.votacion.pk, self.opcion.pk)
        services.emitir_voto(request, self.votacion.pk, self.opcion.pk)
        with self.assertRaises(services.ReglaVoto) as e:
            services.emitir_voto(request, self.votacion.pk, self.opcion.pk)
        self.assertEqual(e.exception.codigo, "frecuencia")

    def test_rn07_los_votos_no_se_editan_desde_el_admin(self):
        modelo_admin = site._registry[Voto]
        request = RequestFactory().get("/")
        request.user = crear_usuario("super@prueba.co", admin=True, is_superuser=True)
        self.assertFalse(modelo_admin.has_add_permission(request))
        self.assertFalse(modelo_admin.has_change_permission(request))
        self.assertFalse(modelo_admin.has_delete_permission(request))


@skipIf(connection.vendor == "sqlite", "La prueba de concurrencia necesita MySQL (SQLite bloquea toda la base).")
class CU04ConcurrenciaTests(TransactionTestCase):
    """CU-04 7b · RNF-05 · R-07: solicitudes simultáneas del mismo votante → un solo voto."""

    @override_settings(VOTOS_MAX_POR_MINUTO=1000)
    def test_solicitudes_simultaneas_registran_un_solo_voto(self):
        cache.clear()
        _, _, votacion = crear_base()
        votante = crear_usuario("rapido@prueba.co")
        opcion = votacion.opciones.first()
        barrera = threading.Barrier(8)
        resultados = []

        def intentar():
            from django.db import connection as conexion_hilo
            request = RequestFactory().post("/")
            request.user = votante
            barrera.wait()
            try:
                services.emitir_voto(request, votacion.pk, opcion.pk)
                resultados.append("ok")
            except services.ReglaVoto as e:
                resultados.append(e.codigo)
            finally:
                conexion_hilo.close()

        hilos = [threading.Thread(target=intentar) for _ in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(resultados.count("ok"), 1, resultados)
        self.assertEqual(Voto.objects.filter(usuario=votante).count(), 1)

    @override_settings(VOTOS_MAX_POR_MINUTO=1000)
    def test_votos_simultaneos_en_votaciones_de_la_misma_categoria(self):
        """Dos votaciones de la misma categoría a la vez: MySQL deja pasar solo un voto."""
        cache.clear()
        _, categoria, votacion = crear_base()
        otra = crear_votacion(categoria, titulo="Mejor presentación en tarima")
        votante = crear_usuario("doble@prueba.co")
        barrera = threading.Barrier(8)
        resultados = []

        def intentar(v):
            from django.db import connection as conexion_hilo
            request = RequestFactory().post("/")
            request.user = votante
            barrera.wait()
            try:
                services.emitir_voto(request, v.pk, v.opciones.first().pk)
                resultados.append("ok")
            except services.ReglaVoto as e:
                resultados.append(e.codigo)
            finally:
                conexion_hilo.close()

        hilos = [threading.Thread(target=intentar, args=(votacion if i % 2 else otra,)) for i in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(resultados.count("ok"), 1, resultados)
        self.assertEqual(Voto.objects.filter(usuario=votante, categoria=categoria).count(), 1)


class CU07GestionVotacionesTests(BaseVoto):
    def setUp(self):
        super().setUp()
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")

    def estado(self, votacion, accion):
        return self.client.post(f"/panel/votaciones/{votacion.pk}/estado/", {"accion": accion}, follow=True)

    def test_crear_queda_en_borrador(self):
        self.client.post("/panel/votaciones/", {"titulo": "Mejor piquero", "categoria": self.categoria.pk})
        v = Votacion.objects.get(titulo="Mejor piquero")
        self.assertEqual(v.estado, Votacion.BORRADOR)
        self.assertTrue(RegistroAuditoria.objects.filter(accion__contains="creada en borrador").exists())

    def test_rn09_abrir_requiere_dos_opciones_activas(self):
        v = crear_votacion(self.categoria, titulo="Con una", estado=Votacion.BORRADOR, opciones=1)
        self.assertContains(self.estado(v, "abrir"), "al menos 2 opciones activas")
        Opcion.objects.create(votacion=v, nombre="Segunda")
        self.estado(v, "abrir")
        v.refresh_from_db()
        self.assertEqual(v.estado, Votacion.ABIERTA)

    def test_4a_cierre_anterior_a_la_apertura(self):
        datos = {"titulo": "X", "categoria": self.categoria.pk, "descripcion": "", "fecha_apertura": "2027-05-01T10:00",
                 "fecha_cierre": "2027-04-01T10:00", "max_votos_por_votante": 1, "periodicidad_voto": "unica",
                 "resultados_visibles": "cierre"}
        v = crear_votacion(self.categoria, titulo="Fechas", estado=Votacion.BORRADOR)
        r = self.client.post(f"/panel/votaciones/{v.pk}/configurar/", datos, follow=True)
        self.assertContains(r, "La fecha de cierre debe ser posterior a la de apertura.")

    def test_2a_con_votos_no_cambian_las_reglas_criticas(self):
        Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=self.opcion, periodo="UNICA")
        datos = {"titulo": "Nuevo título", "categoria": self.categoria.pk, "descripcion": "d",
                 "fecha_cierre": "2027-05-01T20:00", "max_votos_por_votante": 9, "periodicidad_voto": "diaria",
                 "resultados_visibles": "vivo"}
        self.client.post(f"/panel/votaciones/{self.votacion.pk}/configurar/", datos)
        self.votacion.refresh_from_db()
        self.assertEqual(self.votacion.titulo, "Nuevo título")              # no crítico: cambia
        self.assertEqual(self.votacion.resultados_visibles, "vivo")
        self.assertEqual(self.votacion.max_votos_por_votante, 1)            # crítico: se mantiene
        self.assertEqual(self.votacion.periodicidad_voto, Votacion.UNICA)

    def test_programar_y_apertura_automatica(self):
        v = crear_votacion(self.categoria, titulo="Programada", estado=Votacion.BORRADOR,
                           fecha_apertura=timezone.now() + timedelta(hours=2))
        self.estado(v, "programar")
        v.refresh_from_db()
        self.assertEqual(v.estado, Votacion.PROXIMA)
        Votacion.objects.filter(pk=v.pk).update(fecha_apertura=timezone.now() - timedelta(seconds=1))
        self.client.get("/categorias/")
        v.refresh_from_db()
        self.assertEqual(v.estado, Votacion.ABIERTA)

    def test_cerrar_y_6a_reabrir_pendiente(self):
        self.estado(self.votacion, "cerrar")
        self.votacion.refresh_from_db()
        self.assertEqual(self.votacion.estado, Votacion.CERRADA)
        self.assertContains(self.estado(self.votacion, "reabrir"), "pendiente de validación con el cliente")
        self.votacion.refresh_from_db()
        self.assertEqual(self.votacion.estado, Votacion.CERRADA)

    def test_filtro_por_estado(self):
        crear_votacion(self.categoria, titulo="Solo borrador", estado=Votacion.BORRADOR)
        r = self.client.get("/panel/votaciones/?estado=borrador")
        self.assertContains(r, "Solo borrador")
        self.assertNotContains(r, '<span class="t">Canción favorita</span>')


class CU08GestionOpcionesTests(BaseVoto):
    def setUp(self):
        super().setUp()
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")

    def test_crear_y_4a_nombre_duplicado(self):
        self.client.post("/panel/opciones/nueva/", {"votacion": self.votacion.pk, "nombre": "Opción D"})
        self.assertTrue(self.votacion.opciones.filter(nombre="Opción D").exists())
        r = self.client.post("/panel/opciones/nueva/", {"votacion": self.votacion.pk, "nombre": "opción d"}, follow=True)
        self.assertContains(r, "Ya existe una opción con ese nombre en esta votación.")

    def test_rn10_con_votos_se_desactiva_sin_votos_se_elimina(self):
        Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=self.opcion, periodo="UNICA")
        r = self.client.post(f"/panel/opciones/{self.opcion.pk}/estado/", follow=True)
        self.assertContains(r, "se desactivó en lugar de eliminarse (RN-10)")
        self.opcion.refresh_from_db()
        self.assertFalse(self.opcion.activa)
        # Queda con 2 activas (abierta): ya no se puede quitar otra.
        sin_votos = self.votacion.opciones_activas().last()
        r = self.client.post(f"/panel/opciones/{sin_votos.pk}/estado/", follow=True)
        self.assertContains(r, "necesita al menos 2 opciones activas")
        # Cerrada, la opción sin votos sí se elimina.
        Votacion.objects.filter(pk=self.votacion.pk).update(estado=Votacion.CERRADA)
        self.client.post(f"/panel/opciones/{sin_votos.pk}/estado/")
        self.assertFalse(Opcion.objects.filter(pk=sin_votos.pk).exists())

    def test_ordenar_opciones(self):
        ultima = self.votacion.opciones.last()
        self.client.post(f"/panel/opciones/{ultima.pk}/mover/", {"direccion": "subir"})
        self.assertEqual(list(self.votacion.opciones.values_list("nombre", flat=True)), ["Opción A", "Opción C", "Opción B"])


class UnicidadPorCategoriaTests(BaseVoto):
    """Regla del enunciado: un voto por usuario, categoría y edición; se puede votar en otras categorías."""

    def setUp(self):
        super().setUp()
        # Segunda votación de la MISMA categoría (Música) y una votación de OTRA categoría.
        self.misma_cat = crear_votacion(self.categoria, titulo="Mejor presentación en tarima")
        self.otra_categoria = Categoria.objects.create(edicion=self.edicion, nombre="Piquería", orden=1)
        self.otra_cat = crear_votacion(self.otra_categoria, titulo="Mejor piquero")
        self.entrar()

    def test_no_puede_votar_dos_veces_en_la_misma_categoria(self):
        self.votar()
        # Al intentar elegir una opción en otra votación de Música, el sistema lo detiene.
        r = self.client.post(f"/votaciones/{self.misma_cat.pk}/opciones/", {"opcion": self.misma_cat.opciones.first().pk})
        self.assertRedirects(r, f"/votaciones/{self.misma_cat.pk}/ya-votaste/")
        self.votar(self.misma_cat, self.misma_cat.opciones.first())
        self.assertEqual(Voto.objects.filter(usuario=self.votante, categoria=self.categoria).count(), 1)
        pagina = self.client.get(f"/votaciones/{self.misma_cat.pk}/ya-votaste/")
        self.assertContains(pagina, "Ya votaste en la categoría Música")

    def test_puede_votar_en_otra_categoria_de_la_misma_edicion(self):
        self.votar()
        r = self.votar(self.otra_cat, self.otra_cat.opciones.first())
        self.assertEqual(r.status_code, 302)
        self.assertIn("/comprobante/", r["Location"])
        self.assertEqual(Voto.objects.filter(usuario=self.votante, edicion=self.edicion).count(), 2)

    def test_dos_sesiones_del_mismo_usuario_no_duplican_el_voto(self):
        """Iniciar sesión dos veces (dos navegadores o dispositivos) no permite un segundo voto."""
        from django.test import Client
        otra_sesion = Client()
        otra_sesion.post("/ingresar/", {"correo": "votante@prueba.co", "clave": CLAVE})
        # Ambas sesiones eligen opción antes de que alguna confirme.
        self.client.post(f"/votaciones/{self.votacion.pk}/opciones/", {"opcion": self.opcion.pk})
        otra_sesion.post(f"/votaciones/{self.misma_cat.pk}/opciones/", {"opcion": self.misma_cat.opciones.first().pk})
        self.client.post(f"/votaciones/{self.votacion.pk}/confirmar/")
        r = otra_sesion.post(f"/votaciones/{self.misma_cat.pk}/confirmar/")
        self.assertRedirects(r, f"/votaciones/{self.misma_cat.pk}/ya-votaste/")
        self.assertEqual(Voto.objects.filter(usuario=self.votante).count(), 1)

    def test_mysql_rechaza_el_duplicado_por_categoria_y_edicion(self):
        Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=self.opcion, periodo="UNICA", numero=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(usuario=self.votante, votacion=self.misma_cat, opcion=self.misma_cat.opciones.first(),
                                periodo="UNICA", numero=1)

    def test_el_voto_guarda_la_categoria_y_la_edicion_de_su_votacion(self):
        self.votar(self.otra_cat, self.otra_cat.opciones.first())
        voto = Voto.objects.get(usuario=self.votante)
        self.assertEqual((voto.categoria, voto.edicion), (self.otra_categoria, self.edicion))

    def test_listados_marcan_la_categoria_votada(self):
        self.votar()
        self.assertContains(self.client.get("/categorias/"), "Ya votaste en esta categoría", count=1)
        self.assertContains(self.client.get(f"/categorias/{self.categoria.pk}/"), "Ya votaste", count=2)
        detalle = self.client.get(f"/votaciones/{self.misma_cat.pk}/")
        self.assertContains(detalle, "Ya votaste en esta categoría")
        self.assertFalse(detalle.context["puede_votar"])


class MiParticipacionTests(BaseVoto):
    """Pantalla P-10: el votante ve las categorías en las que ya votó."""

    def test_pide_iniciar_sesion(self):
        r = self.client.get("/mi-participacion/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/ingresar/", r["Location"])

    def test_muestra_categorias_votadas_y_pendientes_sin_la_opcion(self):
        Categoria.objects.create(edicion=self.edicion, nombre="Piquería", orden=1)
        self.entrar()
        self.votar()
        r = self.client.get("/mi-participacion/")
        self.assertContains(r, "Votaste en 1 de 2 categorías")
        self.assertContains(r, "Votada")
        self.assertContains(r, "Pendiente")
        self.assertContains(r, Voto.objects.get().codigo)
        self.assertNotContains(r, self.opcion.nombre)  # voto secreto

    def test_el_administrador_va_al_panel(self):
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")
        self.assertRedirects(self.client.get("/mi-participacion/"), "/panel/")


class ConfiguracionGeneralTests(BaseVoto):
    """A-06: la configuración básica se cambia desde la interfaz y queda en MySQL."""

    DATOS = {"max_intentos_login": 3, "minutos_bloqueo": 10, "votos_por_minuto": 20,
             "max_votos_por_defecto": 1, "periodicidad_por_defecto": "unica", "resultados_por_defecto": "vivo"}

    def test_solo_el_administrador_entra(self):
        self.entrar()
        self.assertNotEqual(self.client.get("/panel/configuracion/").status_code, 200)

    def test_guardar_configuracion_y_auditoria(self):
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")
        self.assertContains(self.client.get("/panel/configuracion/"), "Configuración general")
        r = self.client.post("/panel/configuracion/", self.DATOS, follow=True)
        self.assertContains(r, "Configuración guardada")
        config = Configuracion.objects.get()
        self.assertEqual((config.max_intentos_login, config.resultados_por_defecto), (3, "vivo"))
        self.assertTrue(RegistroAuditoria.objects.filter(accion="Configuración general actualizada").exists())

    def test_valores_fuera_de_rango_no_se_guardan(self):
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")
        self.client.post("/panel/configuracion/", dict(self.DATOS, max_intentos_login=0))
        self.assertFalse(Configuracion.objects.exists())

    def test_las_votaciones_nuevas_toman_los_valores_configurados(self):
        Configuracion.objects.create(max_votos_por_defecto=2, periodicidad_por_defecto="diaria",
                                     resultados_por_defecto="vivo")
        crear_usuario("admin@prueba.co", admin=True)
        self.entrar("admin@prueba.co")
        self.client.post("/panel/votaciones/", {"titulo": "Mejor acordeonero", "categoria": self.categoria.pk})
        v = Votacion.objects.get(titulo="Mejor acordeonero")
        self.assertEqual((v.max_votos_por_votante, v.periodicidad_voto, v.resultados_visibles), (2, "diaria", "vivo"))

    def test_el_bloqueo_de_inicio_de_sesion_usa_la_configuracion(self):
        Configuracion.objects.create(max_intentos_login=2, minutos_bloqueo=7)
        for _ in range(2):
            self.client.post("/ingresar/", {"correo": "votante@prueba.co", "clave": "incorrecta"})
        r = self.client.post("/ingresar/", {"correo": "votante@prueba.co", "clave": CLAVE})
        self.assertContains(r, "Espera 7 minutos")
