# Quiniela RPCI

App web **móvil-first** para gestionar una **quiniela de un solo partido**: cada participante
recibe un marcador distinto (0-0, 1-0, …). Los visitantes se autoasignan un marcador
disponible validándose con los **3 últimos dígitos de su ID**, y un administrador configura
usuarios, participantes y los marcadores posibles.

Prioridades del proyecto (del usuario): **bajo consumo de recursos**, **excelente
visualización en celular** (regla insistente), estética minimalista y con toques de emoción.
UI 100% en **español**.

## Stack

- **Flask + SQLite + SQLAlchemy + Gunicorn**, dockerizado. Elegido sobre Django por menor RAM
  (~40–95 MB) y porque las vistas son a medida. SQLite = un archivo, sin servidor de BD.
- Sin frameworks CSS/JS externos (CSS y JS propios, para peso mínimo y para funcionar bajo el
  CSP de artifacts/producción).

## Cómo correr

```bash
cd /home/administrador/quiniela_rpci
docker compose up -d --build
```

- **⚠️ El puerto 8000 está ocupado en la máquina host (WSL2)** → el compose mapea **`8010:8000`**.
  App en `http://localhost:8010/`. Admin en `/admin`.
- Contraseña admin por defecto: **`admin123`** (env `ADMIN_PASSWORD`). **Aún sin cambiar.**
- **Volúmenes nombrados** `quiniela_db` y `quiniela_uploads` (NO bind-mounts: se usó named
  volumes porque el contenedor corre como `appuser` no-root y un bind-mount `./instance`
  creado por Docker como root rompía SQLite con "unable to open database file").
- **Importante para verificar cambios:** plantillas/CSS/estáticos se **copian dentro de la
  imagen** (no hay bind-mount de código) → hay que **`docker compose build`** tras editar
  templates o CSS para ver los cambios.

## Estructura

```
quiniela_rpci/
  app/
    __init__.py        # app factory: init db, blueprints, create_all, seed Ajustes
    models.py          # Usuario, Match, Participante, Ajustes
    auth.py            # decorador admin_required (sesión + ADMIN_PASSWORD)
    services.py        # generar_matches, reset_matches, borrar_usuarios, asignar_marcador
    routes/
      polla.py         # vista pública Polla_View + /asignar (soporta JSON para la ruleta)
      admin.py         # /admin: login, dashboard, usuarios, participantes, ajustes, match
    templates/
      base.html, polla.html, admin/*.html
    static/ css/style.css, img/logo.svg, uploads/
  config.py            # SECRET_KEY, DB URI, ADMIN_PASSWORD, upload
  wsgi.py              # app = create_app()
  Dockerfile           # python:3.12-slim, gunicorn -w 2, usuario no-root
  docker-compose.yml   # puerto 8010:8000, volúmenes nombrados, env
```

## Modelo de datos (4 tablas)

- **Usuario**: `id` (PK), `nombre_usuario` (**único, NOCASE** — sin duplicados ignorando
  mayúsculas/espacios), `id_usuario` (**único**).
- **Match**: `id`, `local`, `visitante`, `goles_local`, `goles_visitante`, `disponible`.
  `UniqueConstraint` sobre la fila completa.
- **Participante**: `id`, `usuario_id` (FK único), `match_id` (FK **único**, nullable). Enlaza
  quién juega con su marcador. Unicidad de `match_id` ⇒ ningún marcador se repite; nullable ⇒
  "pendiente".
- **Ajustes** (singleton): `equipo_local`, `equipo_visitante`, `max_local`, `max_visitante`,
  `max_global`, `titulo_quiniela`, `logo_filename`, `redirect_url` (nullable; si tiene valor la
  Polla_View redirige a todos allí — ver "Redirigir a todos").

> **Micro-migración de esquema:** `db.create_all()` NO altera tablas ya existentes. Como la BD de
> producción vive en el volumen con datos, `app/__init__.py` tiene `_ensure_schema()` que hace un
> `ALTER TABLE ... ADD COLUMN` idempotente (así se añadió `redirect_url`). Al agregar una columna
> nueva al modelo, añade su ALTER ahí también, o la tabla existente no la tendrá.

## Reglas de negocio

- Cada participante: **un solo** marcador. Ningún marcador se repite. Ninguna fila Match se
  repite. Solo se asignan marcadores **disponibles**; al agotarse → aviso.
- **Generación de Match**: `gl in 0..max_local`, `gv in 0..max_visitante`, se crea solo si
  `gl+gv <= max_global`. Requiere tabla Match vacía (resetear antes).
- **Asignación**: `random.choice` entre disponibles → marca `disponible=False` y setea
  `match_id`. (Sin bloqueo atómico; carrera casi imposible aquí y la unicidad de `match_id`
  es el respaldo.)

## Vistas / features implementadas

**Admin** (`/admin`, protegido por contraseña única):
- Login/logout, dashboard con estado (usuarios, participantes, disponibles, "polla lista").
- CRUD Usuarios (con rechazo de nombre/ID duplicado y mensajes claros).
- Selección de Participantes (checkboxes; no permite quitar a quien ya tiene marcador).
- Ajustes: equipos, máximos de goles, título, **subida de logo** + botón **Generar Match**.
- Match: ver marcadores como chips (disponibles vs. asignados). **Resetear** con doble validación
  (escribir `BORRAR`). Además:
  - **Agregar marcador manual** (form goles local/visitante): se valida que la fila no exista
    (respaldo del `UniqueConstraint`) para no violar la unicidad. `services.agregar_marcador`.
  - **Eliminar un marcador** con la ✕ del chip — **solo si aún NO está asignado** (los asignados
    salen bloqueados con 🔒, sin ✕; y la ruta rechaza el borrado aunque fuercen el POST).
    Al eliminarlo desaparece de "disponibles" en la Polla_View. `services.eliminar_marcador`.
- **Borrar todos los usuarios** con doble validación (conserva Match y libera marcadores).
- **🚨 Redirigir a todos** (interruptor de cierre): el admin fija una `redirect_url` y **todos
  los visitantes con la quiniela abierta** son enviados allí. Implementación: la Polla_View pública
  hace `redirect` server-side si hay URL, y además **sondea `/estado`** (JSON) cada 15 s por JS para
  redirigir las pestañas ya abiertas. Se desactiva desde el mismo card. **No afecta al panel admin.**
  Rutas: `admin.redirigir` (activar/desactivar) y `polla.estado` (sondeo ligero).

**Polla_View** (`/`, pública):
- Encabezado con equipos: **local y visitante en colores distintos** (local azul
  `--team-local`, visitante naranja `--team-visitante`; seguros para daltonismo).
- **Tabla de "Resultados asignados"** con cuadrícula completa (bordes en columnas y filas),
  encabezado y fila de **Total asignados**.
- Lista de **pendientes** (radios) + **barra de acción fija abajo** (siempre visible aunque la
  lista sea larga) con etiqueta compacta "Últ. 3 díg. de tu ID" + campo + botón.
- **Botón "🎲 Asignar resultado"**: verde vibrante con glow (contraste alto).
- **Marcadores**: chips donde el gol local va en color local y el visitante en color
  visitante (en disponibles, asignados y ruleta).
- **Ruleta de asignación** (¡IMPORTANTE, ver memoria [[ruleta-overlay-grande]]): al asignar,
  el JS hace `fetch` a `/asignar` (endpoint devuelve JSON con el marcador elegido) y muestra
  un **overlay a PANTALLA COMPLETA** con marcadores girando ~5 s que aterriza con "pop" en el
  marcador real. El overlay grande es una **preferencia confirmada del usuario** — no
  reducirla. Respeta `prefers-reduced-motion`. Incluye un **badge jocoso "ALGORITMO 100%
  LEGAL"** con un **raponero (SVG inline)** — humor intencional, mantenerlo.
- Validación de los 3 dígitos con mensajes diferenciados (vacío / formato / no coincide;
  el "no coincide" en tono amable recordando que son los últimos 3 del ID).

## Estado actual de los datos

**20 usuarios / 20 participantes / 0 asignados / 25 marcadores disponibles.** Equipos:
**MÉXICO vs INGLATERRA**, máximos `4/4/8`. Listo para arrancar la quiniela real.

## Despliegue (discutido, aún no ejecutado)

- SQLite ⇒ requiere **una sola instancia con disco persistente** (no Fargate/App Runner tal
  cual). En una VM: mapear `"80:8000"` para servir en puerto 80; URL = `http://IP` (sin
  dominio no hay HTTPS sobre IP pelada).
- **Dirección elegida por el usuario: Oracle Cloud "Always Free"**
  (https://www.oracle.com/cloud/free/), shape **VM.Standard.A1.Flex = ARM (aarch64)**, imagen
  **Ubuntu 22.04 LTS (ARM)**. Construir la imagen en la propia VM (`python:3.12-slim` es
  multi-arch). Abrir puerto 80 en **DOS lugares**: Security List del VCN **y** firewall del SO.
- Alternativas mencionadas: AWS Lightsail ($3.50–5/mes, IP estática), EC2 Free Tier.

## Pendientes / TODO

- [ ] **Cambiar `ADMIN_PASSWORD` y `SECRET_KEY`** en docker-compose.yml antes de exponer
  públicamente (con ngrok o en la nube). `SECRET_KEY` firma la cookie de sesión admin.
- [ ] Desplegar en Oracle Always Free (A1 ARM, Ubuntu 22.04) en puerto 80.
- [ ] (Opcional) Compartir por ngrok: `ngrok http 8010` (ngrok está en Windows, no en WSL;
  o instalarlo en WSL). Plan gratis: URL cambia cada reinicio + página intermedia.
- [ ] (Opcional) HTTPS: requiere dominio + reverse-proxy Caddy.

## Convenciones

- Todo el texto de UI en **español**.
- Diseño **mobile-first**: `max-width: 480px`, banner sticky, tipografía system, light+dark.
- Colores por token (CSS custom properties en `:root` + overrides dark). Equipos: `--team-local`
  / `--team-visitante`. Marcador coloreado vía macro Jinja `score(gl, gv)` en `polla.html`.
