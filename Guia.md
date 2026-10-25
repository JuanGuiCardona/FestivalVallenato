Esta guía parte del proyecto festival vallenato, el cual se encuentra alojado en el repositorio de GitHub


Estructura actual del proyecto:

```
Pagina de votaciones/
├── env_platform-festival/
├── plataforma_festival/
│   ├── settings.py            
│   ├── urls.py                 
│   ├── fabrica_pruebas.py      
│   ├── __init__.py, asgi.py, wsgi.py
├── accounts/                   
├── catalog/                    
├── voting/                     
├── results/                    
├── audit/                      
├── templates/                  
├── static/                     
├── .env                        
└── manage.py
```

> Cada vez que se abra una terminal primero se debe de activar el entorno:
> ```
> env_platform-festival\Scripts\activate
> ```
> Debe aparecer `(env_platform-festival)` al inicio de la línea.


## Paso 1 · Instalar las librerías

```
pip install -r requirements.txt
```

Instala tres cosas: **Django**, **mysqlclient** y **python-dotenv** (lee el archivo `.env`).

---

## Paso 2 · Base de datos en MySQL y archivo `.env`

### 2.1 Revisar la versión de MySQL

En MySQL Workbench ejecuta:

```sql
SELECT VERSION();
```

- **8.4 o superior** 
- **8.0.x** Instalar Django 5.2, que es igual de bueno y tiene soporte hasta 2028:
  ```
  pip install "django>=5.2,<6"
  ```
- **XAMPP (MariaDB 10.4)** Instalar MySQL 8.4 desde dev.mysql.com.

### 2.2 Crea la base y el usuario

En MySQL Workbench (conectado como `root`), ejecuta con el rayo ⚡:

```sql
CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'festival'@'localhost' IDENTIFIED BY 'Festival2027';
GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival'@'localhost';
GRANT ALL PRIVILEGES ON test_festival_votaciones.* TO 'festival'@'localhost';
FLUSH PRIVILEGES;
```

La cuarta línea permite que las pruebas automáticas creen su propia base temporal (`test_...`)

> Si en el intento anterior ya se creo la base y el usuario, basta con ejecutar la línea del `test_festival_votaciones` y `FLUSH PRIVILEGES;`.

### 2.3 Crea el archivo `.env`

1. En VS Code, hacer clic derecho en `.env.example` → **Copiar** y luego **Pegar**. Cambia el nombre de la copia a **`.env`** (con el punto al inicio y sin `.example`).
2. Genera una clave secreta en la terminal:
   ```
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
3. Abrir `.env` y se deben de cambiar estas líneas:

   ```
   DJANGO_SECRET_KEY=la-clave-que-salio-en-la-terminal
   DB_PASSWORD=Festival2027
   ```

   `DB_NAME`, `DB_USER` y `DB_PASSWORD` deben ser **idénticos** a los del Paso 2.2.

**¿Por qué un `.env`?** La sección 15.5 del documento pide que las credenciales estén **fuera del código**. Así `settings.py` puede compartirse o subirse a GitHub sin exponer contraseñas (el `.gitignore` ya excluye el `.env`).

---

## Paso 3 · Qué hace `plataforma_festival/settings.py`

| Parte | Qué hace | Documento |
|---|---|---|
| `load_dotenv(...)` | Lee el archivo `.env` | 15.5 |
| `INSTALLED_APPS` | Registra las 5 apps del proyecto | 15.4, RNF-15 |
| `TEMPLATES → DIRS` | Busca `templates/base.html` (el "celular" del prototipo) | 15.1 |
| `DATABASES` | Conexión a MySQL con los datos del `.env` | 15.3 |
| `AUTH_USER_MODEL = "accounts.Usuario"` | Usa la tabla `usuario` de tu diagrama, con su `rol` | Sección 11 |
| `AUTH_PASSWORD_VALIDATORS` | Contraseñas de mínimo 8 caracteres, no comunes, no solo números | RNF-02 |
| `LOGIN_MAX_INTENTOS`, `VOTOS_MAX_POR_MINUTO` | Bloqueo por intentos y límite de solicitudes (preliminar*) | RNF-04 |
| `LANGUAGE_CODE`, `TIME_ZONE` | Español de Colombia y hora de Bogotá | — |
| `STATICFILES_DIRS` | Carpeta `static/` con el CSS, imágenes y JS del prototipo | — |
| Bloque `if not DEBUG` | HTTPS y cookies seguras al publicar | RNF-01 |
| `MESSAGE_TAGS` | Los mensajes de Django salen en el "toast" del prototipo | — |

---

## Paso 4 · Qué hace `plataforma_festival/urls.py`

Conecta las direcciones de cada app:

```python
urlpatterns = [
    path("admin/", admin.site.urls),          # panel técnico de Django
    path("", include("catalog.urls")),        # P-01, P-04, A-02
    path("", include("accounts.urls")),       # P-02, P-03
    path("", include("voting.urls")),         # P-05 a P-09, A-03, A-04
    path("", include("results.urls")),        # resultados, A-01, A-05
]
```

Mapa de pantallas del prototipo → direcciones:

| Pantalla | Dirección | App |
|---|---|---|
| P-01 Inicio | `/` | catalog |
| P-02 Registro | `/registro/` | accounts |
| P-03 Inicio de sesión | `/ingresar/` | accounts |
| P-04 Categorías | `/categorias/` | catalog |
| P-05 Votaciones | `/categorias/<id>/` (y `/resultados/`) | voting / results |
| P-06 Detalle | `/votaciones/<id>/` | voting |
| P-07 Opciones | `/votaciones/<id>/opciones/` | voting |
| P-08 Confirmación | `/votaciones/<id>/confirmar/` | voting |
| P-09 Resultado | `/comprobante/<código>/`, `/votaciones/<id>/ya-votaste/`, `/resultados/<id>/` | voting / results |
| A-01 Panel | `/panel/` | results |
| A-02 Categorías y ediciones | `/panel/categorias/` | catalog |
| A-03 Votaciones | `/panel/votaciones/` | voting |
| A-04 Opciones | `/panel/opciones/` | voting |
| A-05 Resultados y auditoría | `/panel/resultados/` | results |

---

## Paso 5 · Crear las tablas en MySQL

```
python manage.py migrate
```

Las migraciones **ya vienen incluidas** (no hace falta `makemigrations`). Este comando crea en MySQL las tablas del diagrama, con los mismos nombres y llaves:

`edicion`, `categoria`, `votacion`, `opcion`, `voto`, `rol`, `usuario`, `registro_auditoria`

…más las internas de Django (sesiones, permisos). También crea los dos roles: **Votante** y **Administrador**.

Como comprobar en Workbench:

```sql
USE festival_votaciones;
SHOW TABLES;
SELECT * FROM rol;
```

---

## Paso 6 · Cargar los datos del prototipo

```
python manage.py cargar_datos_festival --demo
```

- Crear la **edición 2027** (60° Festival, 28 abr – 1 may 2027) con las categorías, votaciones y opciones del prototipo. Son datos ilustrativos (sección 12.6).
- `--demo` crea las cuentas de prueba del prototipo: `votante@demo.co / demo1234` y `admin@demo.co / admin1234`.

---

## Paso 7 · Crear un administrador

```
python manage.py createsuperuser
```

Solicitara **Correo**, **Nombre** y **Password** (no se ve mientras se escribe; es normal). Queda con rol **Administrador**.

---

## Paso 8 · Encender el sitio

```
python manage.py runserver
```

- **http://127.0.0.1:8000/** → la página de votaciones (tu prototipo, ahora con datos reales).
- Inicia sesión como administrador → te lleva al **Panel (A-01)**.
- **http://127.0.0.1:8000/admin/** → panel técnico de Django (solo lectura para votos y auditoría).

Para apagarlo: **Ctrl + C**.

**Prueba rápida:** regístrarse con un correo nuevo, votar y luego en Workbench:

```sql
SELECT codigo, periodo, fecha_hora FROM voto ORDER BY id_voto DESC LIMIT 5;
SELECT fecha_hora, accion, detalle FROM registro_auditoria ORDER BY id_registro DESC LIMIT 10;
```

---

## Paso 9 · Pruebas automáticas

```
python manage.py test
```

Ejecuta **60 pruebas** organizadas por caso de uso (CU-01 a CU-09), incluidas las de seguridad y la de **votos simultáneos**: 8 solicitudes al mismo tiempo del mismo votante → MySQL registra **una sola**. Tarda entre 1 y 3 minutos y termina en `OK`.

Para probar solo una parte: `python manage.py test voting` (o `accounts`, `catalog`, `results`).

---

## Si aparece un error

| Mensaje | Solución |
|---|---|
| `MySQL 8.4 or later is required` | Tu MySQL es 8.0: `pip install "django>=5.2,<6"` (Paso 2.1) |
| `No module named 'dotenv'` | `pip install -r requirements.txt` |
| `No module named 'accounts'` (o catalog, voting…) | Las carpetas no quedaron al lado de `manage.py` (Paso 1) |
| `Access denied for user 'festival'` | La contraseña del `.env` no coincide con la del Paso 2.2 |
| `Unknown database 'festival_votaciones'` | Ejecuta el SQL del Paso 2.2 |
| `Can't connect to MySQL server` | MySQL está apagado: enciéndelo en Servicios de Windows (MySQL84 o MySQL80) |
| `Falta DJANGO_SECRET_KEY` | No existe el `.env` o falta esa línea (Paso 2.3) |
| `Got an error creating the test database: access denied` | Falta el permiso de `test_festival_votaciones` (Paso 2.2) |
| La página sale sin colores | Revisa que `DJANGO_DEBUG=1` en el `.env` y que la carpeta `static` esté al lado de `manage.py` |
| `InconsistentMigrationHistory` | La base tiene tablas de un intento anterior. En Workbench: `DROP DATABASE festival_votaciones;` y repita el Paso 2.2 y el Paso 6 |