"""Pruebas de CU-03 Consultar categorías y votaciones y CU-06 Gestionar ediciones y categorías.

Ejecutar: python manage.py test catalog
"""
from django.test import TestCase

from audit.models import RegistroAuditoria
from plataforma_festival.fabrica_pruebas import CLAVE, crear_base, crear_usuario, crear_votacion
from voting.models import Votacion

from .models import Categoria, Edicion


class CU03ConsultaPublicaTests(TestCase):
    def test_muestra_solo_edicion_vigente_categorias_activas_y_no_borradores(self):
        edicion, musica, abierta = crear_base()
        crear_votacion(musica, titulo="Borrador oculto", estado=Votacion.BORRADOR)
        inactiva = Categoria.objects.create(edicion=edicion, nombre="Categoría inactiva", estado=Categoria.INACTIVA)
        crear_votacion(inactiva, titulo="De categoría inactiva")
        vieja = Edicion.objects.create(nombre="Edición anterior", anio=2026)
        crear_votacion(Categoria.objects.create(edicion=vieja, nombre="Antigua"), titulo="De otra edición")

        r = self.client.get("/categorias/")
        self.assertContains(r, "Edición 2027")
        self.assertContains(r, "Música")
        self.assertContains(r, "1 votación disponible")
        self.assertNotContains(r, "Categoría inactiva")
        self.assertNotContains(r, "Antigua")

        r = self.client.get("/")
        self.assertContains(r, "Canción favorita")
        for oculto in ("Borrador oculto", "De categoría inactiva", "De otra edición"):
            self.assertNotContains(r, oculto)

    def test_2a_sin_edicion_vigente(self):
        r = self.client.get("/categorias/")
        self.assertContains(r, "Aún no hay categorías publicadas.")
        self.assertContains(self.client.get("/"), "Aún no hay votaciones disponibles.")

    def test_4a_categoria_sin_votaciones(self):
        edicion, _, _ = crear_base()
        vacia = Categoria.objects.create(edicion=edicion, nombre="Vacía")
        self.assertContains(self.client.get(f"/categorias/{vacia.pk}/"), "Esta categoría aún no tiene votaciones.")

    def test_rf05_lista_estado_y_fechas(self):
        _, musica, _ = crear_base()
        r = self.client.get(f"/categorias/{musica.pk}/")
        self.assertContains(r, "Abierta")
        self.assertContains(r, "Cierra:")


class CU06GestionTests(TestCase):
    def setUp(self):
        self.edicion, self.musica, self.votacion = crear_base()
        crear_usuario("admin@prueba.co", admin=True)
        crear_usuario("votante@prueba.co")

    def entrar(self, correo="admin@prueba.co"):
        self.client.post("/ingresar/", {"correo": correo, "clave": CLAVE})

    def test_rn08_solo_administrador(self):
        r = self.client.get("/panel/categorias/")
        self.assertRedirects(r, "/ingresar/?next=%2Fpanel%2Fcategorias%2F", fetch_redirect_response=False)
        self.entrar("votante@prueba.co")
        r = self.client.post("/panel/categorias/nueva/", {"edicion": self.edicion.pk, "nombre": "Intrusa"})
        self.assertFalse(Categoria.objects.filter(nombre="Intrusa").exists())
        self.assertEqual(r.status_code, 302)

    def test_crear_categoria_y_5a_nombre_duplicado(self):
        self.entrar()
        self.client.post("/panel/categorias/nueva/", {"edicion": self.edicion.pk, "nombre": "Piquería"})
        self.assertTrue(Categoria.objects.filter(nombre="Piquería", edicion=self.edicion).exists())
        r = self.client.post("/panel/categorias/nueva/", {"edicion": self.edicion.pk, "nombre": "piquería"}, follow=True)
        self.assertContains(r, "Ya existe una categoría con ese nombre.")
        self.assertEqual(Categoria.objects.filter(nombre__iexact="piquería").count(), 1)
        self.assertTrue(RegistroAuditoria.objects.filter(accion__startswith="Categoría «Piquería» creada").exists())

    def test_3a_no_desactiva_categoria_con_votaciones_abiertas(self):
        self.entrar()
        r = self.client.post(f"/panel/categorias/{self.musica.pk}/estado/", follow=True)
        self.assertContains(r, "No se puede desactivar una categoría con votaciones abiertas.")
        self.musica.refresh_from_db()
        self.assertTrue(self.musica.activa)

    def test_rf12_editar_y_ordenar(self):
        self.entrar()
        otra = Categoria.objects.create(edicion=self.edicion, nombre="Danza", orden=1)
        self.client.post(f"/panel/categorias/{otra.pk}/editar/", {"nombre": "Danza y comparsas", "descripcion": "Desfiles"})
        otra.refresh_from_db()
        self.assertEqual(otra.nombre, "Danza y comparsas")
        self.client.post(f"/panel/categorias/{otra.pk}/mover/", {"direccion": "subir"})
        self.assertEqual(list(self.edicion.categorias.values_list("nombre", flat=True)), ["Danza y comparsas", "Música"])

    def test_rf11_crear_edicion_y_solo_una_vigente(self):
        self.entrar()
        self.client.post("/panel/ediciones/nueva/", {"nombre": "61° Festival", "anio": 2028,
                                                       "fecha_inicio": "2028-04-26", "fecha_fin": "2028-04-30"})
        nueva = Edicion.objects.get(anio=2028)
        self.assertEqual(nueva.estado, Edicion.INACTIVA)  # CU-06 3b: parte vacía e inactiva
        # Con votaciones abiertas en la vigente no se cambia de edición.
        r = self.client.post(f"/panel/ediciones/{nueva.pk}/estado/", follow=True)
        self.assertContains(r, "Hay votaciones abiertas en la edición vigente")
        self.votacion.estado = Votacion.CERRADA
        self.votacion.save()
        self.client.post(f"/panel/ediciones/{nueva.pk}/estado/")
        self.assertEqual(Edicion.vigente(), nueva)
        self.assertEqual(Edicion.objects.filter(estado=Edicion.ACTIVA).count(), 1)

    def test_rf11_validaciones_de_edicion(self):
        self.entrar()
        r = self.client.post("/panel/ediciones/nueva/", {"nombre": "Repetida", "anio": 2027}, follow=True)
        self.assertContains(r, "Ya existe una edición de ese año.")
        r = self.client.post("/panel/ediciones/nueva/", {"nombre": "Fechas", "anio": 2030,
                                                           "fecha_inicio": "2030-05-01", "fecha_fin": "2030-04-01"}, follow=True)
        self.assertContains(r, "La fecha de fin no puede ser anterior a la de inicio.")

    def test_filtro_por_estado(self):
        self.entrar()
        Categoria.objects.create(edicion=self.edicion, nombre="Apagada", estado=Categoria.INACTIVA)
        r = self.client.get(f"/panel/categorias/?edicion={self.edicion.pk}&estado=inactiva")
        self.assertContains(r, "Apagada")
        self.assertNotContains(r, "<span class=\"t\">Música</span>")
