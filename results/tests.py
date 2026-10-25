"""Pruebas de CU-05 Consultar resultados públicos y CU-09 Consultar resultados y auditoría.

Ejecutar: python manage.py test results
"""
from django.contrib.admin.sites import site
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from audit.models import RegistroAuditoria
from plataforma_festival.fabrica_pruebas import CLAVE, crear_base, crear_usuario
from voting.models import Votacion, Voto

from .services import calcular


class CU05ResultadosPublicosTests(TestCase):
    def setUp(self):
        _, self.categoria, self.votacion = crear_base()

    def configurar(self, estado, visibles):
        Votacion.objects.filter(pk=self.votacion.pk).update(estado=estado, resultados_visibles=visibles)

    def test_rn11_visibilidad_por_votacion(self):
        casos = [
            (Votacion.ABIERTA, Votacion.RES_VIVO, True),
            (Votacion.ABIERTA, Votacion.RES_CIERRE, False),
            (Votacion.CERRADA, Votacion.RES_CIERRE, True),
            (Votacion.CERRADA, Votacion.RES_ADMIN, False),
        ]
        for estado, visibles, publico in casos:
            with self.subTest(estado=estado, visibles=visibles):
                self.configurar(estado, visibles)
                r = self.client.get(f"/resultados/{self.votacion.pk}/")
                if publico:
                    self.assertContains(r, "Total de votos")
                else:
                    self.assertEqual(r.status_code, 302)  # 2a: «aún no están disponibles»

    def test_listado_de_resultados_publicados(self):
        self.configurar(Votacion.CERRADA, Votacion.RES_CIERRE)
        self.assertContains(self.client.get("/resultados/"), "Canción favorita")
        self.configurar(Votacion.CERRADA, Votacion.RES_ADMIN)
        self.assertContains(self.client.get("/resultados/"), "Aún no hay resultados publicados.")

    def test_3a_sin_votos_muestra_ceros(self):
        self.configurar(Votacion.CERRADA, Votacion.RES_CIERRE)
        r = self.client.get(f"/resultados/{self.votacion.pk}/")
        self.assertContains(r, "0 votos · 0 %")
        self.assertContains(r, "Total de votos: 0")

    def test_calculo_de_porcentajes_y_opcion_lider(self):
        a, b, _ = self.votacion.opciones.all()
        for i, opcion in enumerate([a, a, a, b]):
            Voto.objects.create(usuario=crear_usuario(f"v{i}@prueba.co"), votacion=self.votacion, opcion=opcion, periodo="UNICA")
        Voto.objects.create(usuario=crear_usuario("anulado@prueba.co"), votacion=self.votacion, opcion=b,
                            periodo="UNICA", estado=Voto.ANULADO)
        filas, total = calcular(self.votacion)
        self.assertEqual(total, 4)                       # el anulado no cuenta
        self.assertEqual([f["porcentaje"] for f in filas], [75, 25, 0])
        self.assertEqual([f["lider"] for f in filas], [True, False, False])


class CU09AdministracionTests(TestCase):
    def setUp(self):
        cache.clear()
        _, _, self.votacion = crear_base()
        crear_usuario("admin@prueba.co", admin=True)
        self.votante = crear_usuario("votante@prueba.co")

    def entrar(self, correo="admin@prueba.co"):
        self.client.post("/ingresar/", {"correo": correo, "clave": CLAVE})

    def test_panel_con_indicadores_reales(self):
        Voto.objects.create(usuario=self.votante, votacion=self.votacion, opcion=self.votacion.opciones.first(), periodo="UNICA")
        self.entrar()
        r = self.client.get("/panel/")
        self.assertEqual((r.context["abiertas"], r.context["votos"], r.context["usuarios"]), (1, 1, 2))

    def test_rf15_admin_ve_resultados_aunque_no_sean_publicos(self):
        Votacion.objects.filter(pk=self.votacion.pk).update(resultados_visibles=Votacion.RES_ADMIN)
        self.entrar()
        self.assertContains(self.client.get(f"/panel/resultados/?votacion={self.votacion.pk}"), "Total de votos: 0")
        self.assertContains(self.client.get(f"/resultados/{self.votacion.pk}/"), "Total de votos: 0")

    def test_paso3_filtros_de_auditoria(self):
        self.entrar("votante@prueba.co")
        self.client.post("/salir/")
        self.entrar()
        base = "/panel/resultados/?auditoria=1"
        self.assertContains(self.client.get(base + "&usuario=votante@"), "Inicio de sesión")
        r = self.client.get(base + "&accion=administrador")
        self.assertContains(r, "Inicio de sesión de administrador")
        self.assertNotContains(r, "<b>votante@prueba.co</b>")
        self.assertContains(self.client.get(base + "&desde=2000-01-01&hasta=2000-01-02"), "No hay registros para este filtro.")

    def test_rf17_exportar_csv_solo_admin_y_auditado(self):
        self.entrar("votante@prueba.co")
        self.assertEqual(self.client.get(f"/panel/resultados/{self.votacion.pk}/exportar/").status_code, 302)
        self.client.post("/salir/")
        self.entrar()
        r = self.client.get(f"/panel/resultados/{self.votacion.pk}/exportar/")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Opción A", r.content.decode("utf-8"))
        self.assertTrue(RegistroAuditoria.objects.filter(accion__startswith="Exportación").exists())

    def test_rnf14_la_auditoria_no_se_edita(self):
        modelo_admin = site._registry[RegistroAuditoria]
        request = RequestFactory().get("/")
        request.user = crear_usuario("super@prueba.co", admin=True, is_superuser=True)
        self.assertFalse(modelo_admin.has_change_permission(request))
        self.assertFalse(modelo_admin.has_delete_permission(request))


class ParametrosInvalidosTests(TestCase):
    """Valores escritos a mano en la dirección no deben producir errores del servidor."""

    def test_parametros_no_numericos_se_ignoran(self):
        _, _, votacion = crear_base()
        crear_usuario("admin@prueba.co", admin=True)
        self.client.post("/ingresar/", {"correo": "admin@prueba.co", "clave": CLAVE})
        for url in ("/panel/resultados/?votacion=abc", "/panel/opciones/?votacion=1'or'1", "/panel/categorias/?edicion=x",
                    "/panel/votaciones/?categoria=x&estado=<script>&editar=y"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post("/panel/opciones/nueva/", {"votacion": "abc", "nombre": "X"})
        self.assertEqual(r.status_code, 404)
