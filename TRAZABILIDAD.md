# Trazabilidad: documento (Entrega 1) → código

Esta matriz amplía la **sección 16** del documento hasta el código: para cada requerimiento indica dónde está implementado y qué prueba automática lo comprueba. Responde a la sugerencia del instructor de *conservar la trazabilidad entre requerimientos, casos de uso, modelo de datos e interfaces*.

Convenciones (las mismas del documento):
- **\*** = regla **preliminar** o **pendiente de validación** con el cliente. En la interfaz aparece con asterisco.
- Las pruebas están en `<app>/tests.py`, y sus nombres incluyen el CU o la RN que comprueban.

## 1. Requerimientos funcionales

| RF | Caso de uso | Pantalla → plantilla | Vista (app/views.py) | Entidades | Pruebas |
|---|---|---|---|---|---|
| RF-01 Registro | CU-01 | P-02 → `accounts/p02_registro.html` | `accounts.registro` | Usuario, Rol | `accounts.CU01RegistroTests` |
| RF-02 Iniciar/cerrar sesión por rol | CU-02 | P-03 → `accounts/p03_login.html` | `accounts.iniciar_sesion`, `cerrar_sesion` | Usuario, Rol | `accounts.CU02InicioSesionTests` |
| RF-03 Recuperar contraseña\* | CU-02 2a | P-03 | `accounts.recuperar_clave` (aviso de pendiente) | Usuario | `test_rf03_recuperar_clave_pendiente` |
| RF-04 Categorías activas de la edición vigente | CU-03 | P-01, P-04 → `catalog/p01_inicio.html`, `p04_categorias.html` | `catalog.inicio`, `catalog.categorias` | Edición, Categoría | `catalog.CU03ConsultaPublicaTests` |
| RF-05 Votaciones con estado y fechas | CU-03 | P-05 → `voting/p05_votaciones.html` | `voting.por_categoria` | Categoría, Votación | `test_rf05_lista_estado_y_fechas` |
| RF-06 Detalle y opciones activas | CU-03, CU-04 | P-06, P-07 → `voting/p06_detalle.html`, `p07_opciones.html` | `voting.detalle`, `voting.opciones` | Votación, Opción | `test_opcion_inactiva_no_se_puede_votar` |
| RF-07 Elegir y confirmar explícitamente | CU-04 | P-07, P-08 → `voting/p08_confirmar.html` | `voting.opciones`, `voting.confirmar` | Voto, Opción | `test_flujo_principal_...`, `test_4a_no_elige_opcion` |
| RF-08 Validar reglas antes de registrar | CU-04 | P-08 | `voting/services.py → emitir_voto` | Votación, Voto, Usuario | `voting.CU04EmitirVotoTests`, `CU04ConcurrenciaTests` |
| RF-09 Mensaje posterior y comprobante | CU-04 | P-09 → `voting/p09_comprobante.html`, `p09_ya_voto.html` | `voting.comprobante`, `voting.ya_voto` | Voto | `test_flujo_principal_...`, `test_7a_ya_voto_...` |
| RF-10 Resultados públicos solo si están habilitados\* | CU-05 | P-05, P-09 → `results/p09_resultados.html` | `results.publicos`, `results.votacion` | Votación, Voto, Opción | `results.CU05ResultadosPublicosTests` |
| RF-11 Gestionar ediciones | CU-06 | A-02 → `catalog/a02_categorias.html` | `catalog.admin_edicion_*` | Edición | `test_rf11_*` |
| RF-12 Gestionar categorías (crear, editar, ordenar, activar) | CU-06 | A-02 | `catalog.admin_categoria_*` | Categoría | `catalog.CU06GestionTests` |
| RF-13 Crear/configurar/abrir/cerrar votaciones | CU-07 | A-03 → `voting/a03_votaciones.html` | `voting.admin_votaciones`, `admin_votacion_configurar`, `admin_votacion_estado` | Votación | `voting.CU07GestionVotacionesTests` |
| RF-14 Gestionar opciones (crear, editar, ordenar, desactivar) | CU-08 | A-04 → `voting/a04_opciones.html` | `voting.admin_opcion_*` | Opción | `voting.CU08GestionOpcionesTests` |
| RF-15 Resultados de cualquier votación (admin) | CU-09 | A-05 → `results/a05_resultados.html` | `results.admin_resultados` | Voto, Opción, Votación | `test_rf15_admin_ve_resultados_...` |
| RF-16 Auditoría de acciones críticas | CU-09 | A-05 | `audit/services.py → registrar` (se llama desde todas las vistas) | Registro_Auditoria | `test_paso3_filtros_de_auditoria`, `test_rnf14_*` |
| RF-17 Exportar resultados\* | CU-09 | A-05 | `results.exportar` (CSV preliminar) | Voto, Opción | `test_rf17_exportar_csv_...` |
| (Panel A-01) | CU-06 a CU-09 | A-01 → `results/a01_panel.html` | `results.panel` | — | `test_panel_con_indicadores_reales` |

## 2. Reglas de negocio

| RN | Dónde se aplica | Prueba |
|---|---|---|
| RN-01 Edición → Categoría → Votación → Opción → Voto | Llaves foráneas en `models.py` de catalog y voting | migraciones / todas |
| RN-02 Votación en una sola categoría; categoría en una sola edición | `Votacion.categoria`, `Categoria.edicion` | — |
| RN-03 Opción en una sola votación | `Opcion.votacion` + restricción `opcion_unica_por_votacion` | `test_crear_y_4a_nombre_duplicado` |
| RN-04 Solo vota si está abierta y dentro de fechas | `Votacion.recibe_votos`, `services.sincronizar_estados` | `test_2b_*`, `test_rn04_*`, `test_programar_y_apertura_automatica` |
| RN-05 Votar con cuenta autenticada\* | `voting.opciones` / `confirmar` → redirige a P-03 | `test_2a_sin_sesion_pasa_por_login_y_regresa` |
| RN-06 Límite de votos configurable (única vez, por día)\* | `Votacion.max_votos_por_votante`, `periodicidad_voto`; restricción `voto_unico_por_periodo` | `test_rn06_*`, `test_7b_*`, concurrencia |
| RN-07 El voto confirmado no se modifica\* | No hay pantalla de edición; `VotoAdmin` de solo lectura | `test_rn07_*` |
| RN-08 Solo el administrador gestiona | `accounts/decorators.py → solo_administrador` | `test_rn08_solo_administrador` |
| RN-09 Abrir con al menos 2 opciones activas | `voting.admin_votacion_estado`, `Votacion.sincronizar_estado` | `test_rn09_*` |
| RN-10 Con votos se desactiva, no se elimina | `voting.admin_opcion_estado`; `on_delete=PROTECT`; sin borrar en /admin/ | `test_rn10_*` |
| RN-11 Visibilidad de resultados por votación\* | `Votacion.resultados_visibles`, `resultados_publicos` | `test_rn11_*` |
| RN-12 Autorización de datos (Ley 1581) | `RegistroForm` + `Usuario.acepta_datos` / `fecha_aceptacion` | `test_3a_sin_aceptar_datos_*` |
| RN-13 Cada voto y acción administrativa se audita | `audit.services.registrar` | `test_flujo_principal_*`, `test_crear_categoria_*` |
| RN-14 Un correo por cuenta | `Usuario.correo` único + validación sin mayúsculas | `test_4a_correo_duplicado_*` |
| RN-15 Edad mínima\* | Pendiente: no implementado | — |
| RN-16 Jurados\* | Pendiente: no modelado (11.2) | — |

## 3. Requerimientos no funcionales cubiertos en código

| RNF | Implementación |
|---|---|
| RNF-01 HTTPS y cookies seguras | `settings.py`, bloque `if not DEBUG` |
| RNF-02 Hash de contraseñas | PBKDF2 de Django + validadores de contraseña |
| RNF-03 CSRF, XSS, inyección SQL | `{% csrf_token %}` en todos los formularios POST, autoescape de plantillas, ORM (`test_rnf03_csrf_obligatorio`) |
| RNF-04 Intentos y solicitudes repetitivas\* | `accounts/services.py` (bloqueo), `voting/services.py → _limite_de_solicitudes`, IP en auditoría |
| RNF-05 Voto atómico sin duplicados | `transaction.atomic` + restricción única en MySQL (`CU04ConcurrenciaTests`: 8 solicitudes simultáneas → 1 voto) |
| RNF-07 Consultas indexadas | Índices `votacion_estado_idx` y `voto_conteo_idx` |
| RNF-10 Móvil primero | CSS del prototipo sin cambios (390 px, tableta y computador) |
| RNF-13 Ley 1581 | Aceptación con fecha guardada en `usuario` |
| RNF-14 Auditoría no editable | `RegistroAuditoriaAdmin` sin permisos de cambio ni borrado; sin pantallas de edición |
| RNF-15 Apps modulares | `accounts`, `catalog`, `voting`, `results`, `audit` (sección 15.4) |
| RNF-16 Configurable sin tocar código | Fechas, límite, periodicidad y visibilidad se configuran en A-03 |

## 4. Modelo de datos: diagrama → tablas MySQL

| Entidad del diagrama | Tabla | Campos del diagrama | Campos agregados (y por qué) |
|---|---|---|---|
| Edición | `edicion` | id_edicion, nombre, año (`anio`), fecha_inicio, fecha_fin, estado | — |
| Categoría | `categoria` | id_categoria, id_edicion, nombre, descripcion, orden, estado | — |
| Votación | `votacion` | id_votacion, id_categoria, titulo, descripcion, fecha_apertura, fecha_cierre, estado, max_votos_por_votante, periodicidad_voto, resultados_visibles | fecha_creacion (orden y auditoría) |
| Opción | `opcion` | id_opcion, id_votacion, nombre, descripcion, orden, estado | — |
| Voto | `voto` | id_voto, id_usuario, id_votacion, id_opcion, fecha_hora, estado | `periodo` y `numero` (restricción única de la sección 11.2), `codigo` (comprobante, RF-09) |
| Rol | `rol` | id_rol, nombre | — |
| Usuario | `usuario` | id_usuario, id_rol, nombre, correo, contraseña (`password`, con hash), estado | acepta_datos y fecha_aceptacion (11.2, RN-12), ciudad\* (dato adicional del prototipo), fecha_registro, last_login, is_superuser (internos de Django) |
| Registro_Auditoria | `registro_auditoria` | id_registro, id_usuario, accion, fecha_hora, detalle | ip (RNF-04: detectar patrones) |

## 5. Decisiones del equipo marcadas como preliminares\*

Se pueden cambiar sin tocar el código (desde A-03, A-02 o el archivo `.env`) cuando el cliente las confirme:

- Límite de votos y periodicidad (RN-06). Valor por defecto: 1 voto, una única vez.
- Visibilidad de resultados (RN-11). Valor por defecto: al cierre.
- Bloqueo por intentos: 5 intentos y 5 minutos (`.env`).
- Límite de 10 votos por minuto por persona (`.env`).
- Solo una edición vigente a la vez.
- Las cuentas de administrador no votan (separación de roles, riesgo R-09).
- Con votos registrados no se cambian la categoría, la apertura, el límite ni la periodicidad (CU-07 2a).
- Exportación en CSV (RF-17); el formato definitivo lo decide el cliente.
- Comprobante con código `FV27-XXXXXXXX` (idea de Helios Voting).

## 6. Diferencias con el documento que conviene registrar

1. **Bootstrap (secciones 12.1 y 15.1).** Se conservó el CSS propio del prototipo navegable (`static/css/prototipo.css`) para que la interfaz sea idéntica a la aprobada. Agregar Bootstrap encima chocaría con sus clases (`.btn`, `.card`). Sugerencia: actualizar el texto del documento a "HTML5 + CSS3 propio del prototipo, responsive".
2. **Imagen opcional de la opción (CU-08 paso 3).** No se implementó porque depende de la pregunta P-07 al cliente.
3. **Acceso "administrador (demostración)\*" del prototipo (12.7).** Se reemplazó por el inicio de sesión real con redirección por rol.
