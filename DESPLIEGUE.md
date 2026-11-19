# Publicación del sistema en un servidor

Guía para publicar el Sistema Web de Votaciones en un servidor real, por ejemplo en el subdominio del Festival (documento, sección 15.2). Para trabajar en un computador local, siga [`GUIA.md`](GUIA.md).

## 1. Qué cambia frente al computador local

| Tema | En local | En el servidor |
|---|---|---|
| Modo | `DJANGO_DEBUG=1` | `DJANGO_DEBUG=0`: oculta los errores técnicos y activa HTTPS, cookies seguras y HSTS |
| Servidor web | `python manage.py runserver` (solo para desarrollo) | **Gunicorn** (Linux) o **Waitress** (Windows), detrás de **Nginx** o **IIS** con HTTPS |
| Archivos estáticos | Los entrega `runserver` | `collectstatic` y **WhiteNoise** (o Nginx) |
| Contadores de seguridad | Memoria del proceso | `CACHE_BACKEND=db`: tabla compartida en MySQL, para que el bloqueo por intentos y el freno de votos funcionen con varios procesos |
| Conexiones a MySQL | Una por petición | `DB_CONN_MAX_AGE=60`: se reutilizan |
| IP del cliente | `REMOTE_ADDR` | Con proxy delante, `DJANGO_DETRAS_DE_PROXY=1`; si no, se ignora `X-Forwarded-For` para que nadie falsifique su IP |

## 2. Pasos en un servidor Linux (Ubuntu)

```bash
# 1. Código y entorno
git clone https://github.com/JuanGuiCardona/FestivalVallenato.git
cd FestivalVallenato
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-produccion.txt

# 2. MySQL 8.4: base y usuario propio, solo con permisos sobre esa base
#    CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#    CREATE USER 'festival'@'localhost' IDENTIFIED BY '<contraseña larga>';
#    GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival'@'localhost';

# 3. Archivo .env (copiar .env.example y cambiar):
#    DJANGO_SECRET_KEY=<nueva, generada en el servidor>
#    DJANGO_DEBUG=0
#    DJANGO_ALLOWED_HOSTS=votaciones.festivalvallenato.com
#    DJANGO_CSRF_TRUSTED_ORIGINS=https://votaciones.festivalvallenato.com
#    DJANGO_DETRAS_DE_PROXY=1
#    CACHE_BACKEND=db
#    DB_PASSWORD=<la del paso 2>

# 4. Preparar la base y los archivos
python manage.py migrate
python manage.py createcachetable
python manage.py collectstatic --noinput
python manage.py createsuperuser          # cuenta del administrador real
python manage.py check --deploy           # revisión de seguridad de Django

# 5. Iniciar (como servicio de systemd en producción)
gunicorn plataforma_festival.wsgi --workers 4 --threads 4 --bind 127.0.0.1:8000
```

Nginx recibe las conexiones HTTPS (certificado de Let's Encrypt) y las pasa a Gunicorn:

```nginx
server {
    listen 443 ssl;
    server_name votaciones.festivalvallenato.com;
    # ssl_certificate y ssl_certificate_key de Let's Encrypt
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

En Windows Server se usa `waitress-serve --listen=127.0.0.1:8000 --threads=16 plataforma_festival.wsgi:application` detrás de IIS con el certificado.

**No use la cuenta de demostración en el servidor.** `cargar_datos_festival --demo` crea cuentas con contraseñas conocidas (`admin1234`); en producción solo se crea el administrador real con `createsuperuser`, y el contenido se carga desde el panel.

## 3. Seguridad

- **HTTPS obligatorio:** con `DJANGO_DEBUG=0`, Django redirige a HTTPS, marca las cookies como seguras y envía HSTS por 30 días.
- **Secretos fuera del código:** la clave secreta y la contraseña de MySQL solo están en el `.env` del servidor, que no se sube a GitHub.
- **Usuario de MySQL con permisos mínimos:** solo sobre `festival_votaciones`, nunca `root`.
- **IP confiable:** `X-Forwarded-For` solo se acepta detrás de un proxy propio (`DJANGO_DETRAS_DE_PROXY=1`), y se toma el valor que agrega ese proxy. Así no se puede saltar el bloqueo por intentos cambiando el encabezado. Hay una prueba automática para esto.
- **Revisión de Django:** `python manage.py check --deploy` solo deja dos avisos, que dependen del dominio del Festival: `SECURE_HSTS_INCLUDE_SUBDOMAINS` y `SECURE_HSTS_PRELOAD`. Se activan solo si todos los subdominios del Festival usan HTTPS (`DJANGO_HSTS_SUBDOMINIOS=1`).
- **Copias de seguridad:** un `mysqldump` diario programado, guardado fuera del servidor:
  ```bash
  mysqldump --single-transaction -u festival -p festival_votaciones > respaldo_$(date +%F).sql
  ```

## 4. Muchos votantes al mismo tiempo

**Regla del voto con concurrencia.** La restricción única `voto_unico_usuario_categoria_edicion` de MySQL garantiza un voto por usuario, categoría y edición aunque lleguen muchas solicitudes a la vez. Para comprobarlo directamente en la base del servidor:

```bash
python manage.py simular_votacion --usuarios 30 --intentos 4
```

El comando crea 30 votantes temporales que envían 120 votos al mismo tiempo, verifica en MySQL que cada uno quedó con un solo voto y borra los datos de la simulación. En las pruebas del equipo, 200 votos simultáneos de 50 votantes dejaron exactamente 50 votos y 150 duplicados rechazados, en cerca de 1 segundo.

Cada solicitud simultánea usa su propia conexión a MySQL, así que usuarios × intentos debe ser menor que `max_connections` (151 por defecto en MySQL). Con más, el comando se detiene antes de empezar y sugiere valores. Para probar 200 a la vez, suba el límite en MySQL: `SET GLOBAL max_connections = 300;`.

**Capacidad medida.** En un equipo de 2 núcleos con Gunicorn (4 procesos × 4 hilos) y MySQL, con 100 usuarios simultáneos que hacen 20 peticiones cada uno:

| Página | Peticiones por segundo | Mediana | Percentil 95 | Errores |
|---|---|---|---|---|
| API `/api/categorias/` | 278 | 273 ms | 531 ms | 0 |
| Categorías `/categorias/` | 307 | 222 ms | 568 ms | 0 |
| Inicio `/` | 305 | 252 ms | 463 ms | 0 |

Son valores de referencia: el cliente de la prueba corría en la misma máquina. Antes del Festival conviene repetir la medición en el servidor real.

**Recomendaciones de capacidad:**
- Procesos de Gunicorn: `2 × núcleos + 1`, cada uno con 4 hilos.
- MySQL: `max_connections` mayor que procesos × hilos (por ejemplo 200), e índices ya creados por las migraciones (`votacion_estado_idx`, `voto_conteo_idx` y la restricción única).
- `CACHE_BACKEND=db` es suficiente para el volumen del Festival; para decenas de miles de votantes simultáneos se puede cambiar a Redis sin tocar el código de la aplicación.
- El freno de solicitudes (`votos por minuto` en Configuración general) protege el servidor de clics repetidos o scripts.
