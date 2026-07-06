# Quiniela RPCI

App web minimalista y móvil-first para gestionar una **quiniela de un solo partido**:
cada participante recibe un marcador distinto (0-0, 1-0, …), autoasignándose tras
validarse con los 3 últimos dígitos de su ID.

Stack: **Flask + SQLite + SQLAlchemy + Gunicorn**, dockerizado. Ligero (~40–60 MB RAM).

## Correr con Docker

```bash
docker compose up --build
```

Abrir http://localhost:8000

- **Polla_View** (pública): `/`
- **Admin**: `/admin` (contraseña por defecto `admin123`)

Cambia `SECRET_KEY` y `ADMIN_PASSWORD` en `docker-compose.yml` antes de producción.
La base de datos SQLite persiste en `./instance/quiniela.db` y los logos en
`./app/static/uploads/` (volúmenes montados).

## Correr en local (sin Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py          # http://localhost:8000 (modo debug)
```

## Flujo de uso

1. **Admin → Usuarios**: crea la lista maestra (nombre + ID).
2. **Admin → Participantes**: marca quiénes juegan la quiniela actual.
3. **Admin → Ajustes**: nombres de equipos, máximos de goles (local/visitante/global),
   título y logo. Luego **Generar marcadores** (crea la tabla Match).
4. **Polla_View** (`/`): cada visitante elige un participante pendiente, escribe los
   3 últimos dígitos de su ID y el sistema le asigna un marcador disponible al azar.
5. **Admin → Match**: ver marcadores; **Resetear** (doble confirmación, escribir `BORRAR`)
   para empezar una quiniela nueva.

## Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Clave de sesión Flask | `dev-change-me-please` |
| `ADMIN_PASSWORD` | Contraseña del panel admin | `admin123` |
| `DATABASE_URL` | URI SQLAlchemy | SQLite en `instance/quiniela.db` |

## Reglas garantizadas

- Cada participante tiene **un solo** marcador.
- Ningún marcador se repite entre participantes (`match_id` único).
- Ninguna fila de Match se repite (restricción única sobre la fila completa).
- Solo se asignan marcadores **disponibles**; al agotarse se avisa por popup.
- Al generar Match se excluyen marcadores cuya suma supere el máximo global.
