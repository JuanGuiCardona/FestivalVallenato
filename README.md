# FestivalVallenato · Sistema Web de Votaciones

Plataforma funcional de votaciones para el Festival de la Leyenda Vallenata 2027. Proyecto de **Desarrollo Web** (Fundación Universitaria del Área Andina): plataforma configurable para gestionar ediciones, categorías, votaciones, opciones y votos del Festival.

**Equipo:** Juan Guillermo Cardona Cifuentes · Didier Yovani Combita Pérez · Javier Alexander Puentes Bejarano

- **Tecnologías:** Python 3.11 o superior, Django 6.1 (patrón MVT; compatible con 5.2), MySQL 8.4, HTML5, CSS3 y JavaScript.
- **Dependencias** (`requirements.txt`): `Django>=5.2,<6.2`, `mysqlclient>=2.2` y `python-dotenv>=1.0`.
- **Organización:** 6 apps Django: `accounts`, `catalog`, `voting`, `results` y `audit` (sección 15.4 del documento) y `api` (API GET en JSON).
- **Interfaz:** las pantallas del prototipo navegable (P-01 a P-09 y A-01 a A-05), más *Mi participación* (P-10) y *Configuración general* (A-06).
- **Trazabilidad requerimiento → código → prueba:** ver [`TRAZABILIDAD.md`](TRAZABILIDAD.md).

### Dónde está cada parte clave

| Qué | Archivo |
|---|---|
| **API** `GET /api/categorias/` | `api/views.py` (rutas en `api/urls.py`) |
| **Unicidad del voto** (un voto por usuario, categoría y edición) | Restricción `voto_unico_categoria_edicion` en `voting/models.py` (clase `Voto`) y validación en `voting/services.py → emitir_voto` |
| Migración que crea esa restricción en MySQL | `voting/migrations/0002_voto_unico_por_categoria.py` |
| Categorías votadas por el usuario | `voting/views.py → mi_participacion` (pantalla P-10, `/mi-participacion/`) |
| Configuración desde la interfaz | `voting/views.py → admin_configuracion` (pantalla A-06, `/panel/configuracion/`) |

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

Siga [`GUIA.md`](GUIA.md) paso a paso. Requiere MySQL 8.4 o superior; con MySQL 8.0, use Django 5.2. Resumen:

1. En MySQL, cree la base y un usuario propio para la aplicación (cambie la contraseña):
   ```sql
   CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'festival'@'localhost' IDENTIFIED BY 'una-contrasena-segura';
   GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival'@'localhost';
   ```
2. Copie [`.env.example`](.env.example) como `.env` y escriba sus datos. El `.env` real no se sube al repositorio.
3. Instale, cree las tablas (migraciones), cargue los datos de prueba e inicie el servidor:
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py cargar_datos_festival --demo
   python manage.py runserver
   ```

Las tablas se crean con los nombres del modelo entidad-relación: `edicion`, `categoria`, `votacion`, `opcion`, `voto`, `rol`, `usuario` y `registro_auditoria`, más `configuracion` (A-06).

---

## API GET de categorías

Con el servidor encendido, abra en el navegador o en Postman:

- **http://127.0.0.1:8000/api/categorias/**: categorías activas de la edición vigente, con sus votaciones y opciones, en JSON leído de MySQL.
- **http://127.0.0.1:8000/api/categorias/1/**: una sola categoría.

Es de solo lectura (solo acepta GET) y no entrega votos ni datos personales. Ejemplo resumido de la respuesta:

```json
{
  "edicion": {"id": 1, "nombre": "60° Festival de la Leyenda Vallenata", "anio": 2027},
  "total_categorias": 4,
  "categorias": [
    {
      "id": 1, "nombre": "Música", "estado": "activa",
      "votaciones": [
        {"id": 1, "titulo": "Canción favorita del público", "estado": "abierta",
         "opciones": [{"id": 1, "nombre": "Canción A"}, {"id": 2, "nombre": "Canción B"}]}
      ],
      "opciones": [{"id": 1, "nombre": "Canción A", "id_votacion": 1}]
    }
  ]
}
```

## Configuración desde la interfaz (sin tocar el código)

Con la cuenta de administrador, desde el **Panel (A-01)**:

- **Ediciones y categorías (A-02):** crear, editar, ordenar, activar o desactivar ediciones y categorías.
- **Votaciones (A-03):** crear votaciones, configurar fechas, límite de votos, periodicidad y visibilidad de resultados; abrir y cerrar.
- **Opciones (A-04):** crear, editar, ordenar y desactivar opciones.
- **Configuración general (A-06):** intentos de inicio de sesión, minutos de bloqueo, solicitudes de voto por minuto y reglas iniciales de las votaciones nuevas. Se guarda en la tabla `configuracion` de MySQL.

---

## Pruebas automáticas

```bash
python manage.py test
```

Son 81 pruebas organizadas por caso de uso (CU-01 a CU-09), más las de la API, la regla de un voto por categoría, *Mi participación* y la configuración general. Las 2 pruebas de **votos simultáneos** solo se ejecutan con MySQL; en SQLite se omiten.

## Recorrido sugerido

1. **Visitante:** Inicio → Ver categorías → Música → *Canción favorita del público* (detalle con estado, cierre y límite).
2. **Votante:** Ver opciones y votar → pide iniciar sesión → regresa a la votación → elegir → confirmar → **comprobante**. Si intenta votar otra vez en la misma categoría, aunque sea en otra votación o desde otra sesión, aparece *"Ya votaste en la categoría"*. En las demás categorías sí puede votar. En **Mis votos** ve las categorías en las que ya participó.
3. **Administrador:** Panel → Votaciones → crear una votación → abrirla sin opciones (la bloquea la regla **RN-09**) → agregar 2 opciones → abrirla → Resultados → **registro de auditoría** → **Configuración general**.
4. **API:** abrir `/api/categorias/` y ver el JSON.

Las reglas marcadas con **\*** son preliminares, pendientes de validación con el cliente, como se acordó en el documento de la Entrega 1.