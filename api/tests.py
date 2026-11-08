"""Pruebas de la API GET /api/categorias/ (JSON desde la base de datos)."""
from django.test import TestCase

from catalog.models import Categoria, Edicion
from plataforma_festival.fabrica_pruebas import crear_base, crear_usuario, crear_votacion
from voting.models import Opcion, Votacion, Voto


class ApiCategoriasTests(TestCase):
    def setUp(self):
        self.edicion, self.categoria, self.votacion = crear_base()

    def test_entrega_json_con_categorias_votaciones_y_opciones(self):
        r = self.client.get("/api/categorias/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        datos = r.json()
        self.assertEqual(datos["edicion"]["anio"], 2027)
        self.assertEqual(datos["total_categorias"], 1)
        categoria = datos["categorias"][0]
        self.assertEqual(categoria["nombre"], "Música")
        self.assertEqual(categoria["votaciones"][0]["titulo"], "Canción favorita")
        self.assertEqual([o["nombre"] for o in categoria["opciones"]], ["Opción A", "Opción B", "Opción C"])
        self.assertEqual(categoria["opciones"][0]["id_votacion"], self.votacion.pk)

    def test_solo_datos_publicos(self):
        Categoria.objects.create(edicion=self.edicion, nombre="Inactiva", estado=Categoria.INACTIVA)
        crear_votacion(self.categoria, titulo="En preparación", estado=Votacion.BORRADOR)
        Opcion.objects.filter(nombre="Opción C").update(estado=Opcion.INACTIVA)
        otra = Edicion.objects.create(nombre="Edición anterior", anio=2026, estado=Edicion.INACTIVA)
        Categoria.objects.create(edicion=otra, nombre="Vieja")
        datos = self.client.get("/api/categorias/").json()
        self.assertEqual([c["nombre"] for c in datos["categorias"]], ["Música"])
        self.assertEqual([v["titulo"] for v in datos["categorias"][0]["votaciones"]], ["Canción favorita"])
        self.assertEqual(len(datos["categorias"][0]["opciones"]), 2)

    def test_no_expone_votos_ni_usuarios(self):
        votante = crear_usuario()
        Voto.objects.create(usuario=votante, votacion=self.votacion, opcion=self.votacion.opciones.first(),
                            periodo="UNICA", numero=1)
        texto = self.client.get("/api/categorias/").content.decode()
        self.assertNotIn(votante.correo, texto)
        self.assertNotIn("votos", self.client.get("/api/categorias/").json()["categorias"][0])

    def test_detalle_de_una_categoria(self):
        r = self.client.get(f"/api/categorias/{self.categoria.pk}/")
        self.assertEqual(r.json()["nombre"], "Música")
        r = self.client.get("/api/categorias/99999/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.json())

    def test_solo_permite_get(self):
        self.assertEqual(self.client.post("/api/categorias/").status_code, 405)

    def test_sin_edicion_vigente(self):
        Edicion.objects.update(estado=Edicion.INACTIVA)
        datos = self.client.get("/api/categorias/").json()
        self.assertEqual((datos["edicion"], datos["categorias"]), (None, []))
