# FestivalVallenato
Plataforma funcional de votaciones
# Sistema Web de Votaciones · Festival de la Leyenda Vallenata 2027

Proyecto de **Desarrollo Web** (Fundación Universitaria del Área Andina): plataforma configurable para gestionar ediciones, categorías, votaciones, opciones y votos del Festival.

**Equipo:** Juan Guillermo Cardona Cifuentes · Didier Yovani Combita Pérez · Javier Alexander Puentes Bejarano

- **Tecnologías:** Python, Django (patrón MVT), MySQL, HTML5, CSS3 y JavaScript.
- **Organización:** 5 apps Django, según la sección 15.4 del documento: `accounts`, `catalog`, `voting`, `results` y `audit`.
- **Interfaz:** las 14 pantallas del prototipo navegable (P-01 a P-09 y A-01 a A-05).

---

## Opción 1 · Revisión rápida en Windows (doble clic, sin MySQL)

Solo necesita **Python 3.11 o superior** ([python.org](https://www.python.org/downloads/)). Al instalarlo, marque *"Add python.exe to PATH"*.

1. Descargue el repositorio: botón verde **Code → Download ZIP**, y descomprímalo.
2. Haga **doble clic en `iniciar_demo.bat`**.

El script crea un entorno virtual, instala Django, crea una base de datos local de demostración (SQLite), carga los datos del prototipo y abre **http://127.0.0.1:8000/** en el navegador.

| Rol | Correo | Contraseña |
|---|---|---|
| Votante | `votante@demo.co` | `demo1234` |
| Administrador | `admin@demo.co` | `admin1234` |

Con la cuenta de administrador, el sistema lleva directamente al **Panel (A-01)**.

## Opción 2 · Revisión manual (Windows, macOS o Linux, sin MySQL)

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install "Django>=5.2,<6.2" python-dotenv
```

Cree un archivo `.env` al lado de `manage.py` con este contenido:

```
DJANGO_DEBUG=1
DB_ENGINE=sqlite
```

Después ejecute:

```bash
python manage.py migrate
python manage.py cargar_datos_festival --demo
python manage.py runserver
```

## Opción 3 · Con MySQL (configuración completa del proyecto)

Siga [`GUIA.md`](GUIA.md) paso a paso. Requiere MySQL 8.4 o superior; con MySQL 8.0, use Django 5.2. Las tablas se crean con los nombres del modelo entidad-relación: `edicion`, `categoria`, `votacion`, `opcion`, `voto`, `rol`, `usuario` y `registro_auditoria`.

---

## Pruebas automáticas

```bash
python manage.py test
```

Son 60 pruebas organizadas por caso de uso (CU-01 a CU-09). La prueba de **votos simultáneos** solo se ejecuta con MySQL; en SQLite se omite.

## Recorrido sugerido

1. **Visitante:** Inicio → Ver categorías → Música → *Canción favorita del público* (detalle con estado, cierre y límite).
2. **Votante:** Ver opciones y votar → pide iniciar sesión → regresa a la votación → elegir → confirmar → **comprobante**. Si vuelve a votar, aparece *"Ya votaste"* (un voto por persona).
3. **Administrador:** Panel → Votaciones → crear una votación → abrirla sin opciones (la bloquea la regla **RN-09**) → agregar 2 opciones → abrirla → Resultados → **registro de auditoría**.

Las reglas marcadas con **\*** son preliminares, pendientes de validación con el cliente, como se acordó en el documento de la Entrega 1.
