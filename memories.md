# 📓 Memorias — Volumen persistente en Fly.io (Quiniela RPCI)

Guía para crear/gestionar el **volumen persistente** donde vive la base de datos SQLite
(y los logos subidos). Sin volumen, los datos se borran en cada reinicio/redeploy.

## Datos de esta app (constantes)

| Dato | Valor |
|---|---|
| App | `quiniela-interna-rpci` |
| Región | `ams` (Ámsterdam) |
| Nombre del volumen | `quiniela_data` |
| Punto de montaje | `/app/instance` (declarado en `fly.toml → [mounts]`) |
| Tamaño | **1 GB** (mínimo que permite Fly; ~$0.15/mes) |

> Ya tienes cuenta/suscripción en Fly.io, así que solo necesitas el CLI instalado y logueado.

---

## 0) Instalar `flyctl` (una sola vez)

`flyctl` y `fly` son **el mismo comando** (`fly` es el alias corto).

### En WSL (Ubuntu)
```bash
curl -L https://fly.io/install.sh | sh
# Agrega al PATH (una vez) en ~/.bashrc:
export FLYCTL_INSTALL="$HOME/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"
# recarga:
source ~/.bashrc
fly version
```

### En Windows 11 (PowerShell)
```powershell
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
# o con Scoop:
scoop install flyctl
fly version
```

---

## 1) Autenticarse (una sola vez por máquina)
```bash
fly auth login
```
Abre el navegador y te logueas con tu cuenta de Fly. (Funciona igual en WSL y Windows.)

Verifica:
```bash
fly auth whoami
```

---

## 2) Ubicarse en la carpeta del proyecto (con el fly.toml)

Los comandos leen el `fly.toml` de la carpeta actual. Si no estás en ella, da el error
*"missing an app name"*.

- **WSL:** `cd /home/administrador/quiniela_rpci`
- **Windows:** `cd C:\ruta\a\quiniela_rpci`

> Alternativa: agrega `-a quiniela-interna-rpci` a cualquier comando para no depender de la carpeta.

---

## 3) Crear el volumen
```bash
fly volumes create quiniela_data --size 1 --region ams -a quiniela-interna-rpci
```
- El **nombre** (`quiniela_data`) debe ser **idéntico** al `source` del `fly.toml`.
- Si pregunta por redundancia/"only 1 volume", confirma (para SQLite basta 1).

---

## 4) Confirmar que el fly.toml lo monta

En `fly.toml` debe existir (usa el **NOMBRE**, no el ID del volumen):
```toml
[mounts]
  source = 'quiniela_data'
  destination = '/app/instance'
```

---

## 5) Desplegar
```bash
fly deploy
```

---

## 6) Verificar
```bash
fly volumes list -a quiniela-interna-rpci     # debe salir quiniela_data, attached
fly logs                                       # sin "unable to open database file"
```
Prueba de persistencia:
```bash
# crea datos en el sitio, luego:
fly apps restart quiniela-interna-rpci
# recarga la web: los datos deben seguir ahí
```

---

## ⚠️ Errores comunes (y solución)

- **"missing an app name"** → no estás en la carpeta del `fly.toml`, o falta la línea
  `app = 'quiniela-interna-rpci'`. Solución: `cd` a la carpeta o usa `-a quiniela-interna-rpci`.
- **"can't update the attached volume ... by 'X'"** → el `source` del `fly.toml` no coincide
  con el **nombre real** del volumen. Solución: `fly volumes list` y pon en `source` el NAME exacto.
  (Debe ser el **nombre**, nunca el ID `vol_...`.)
- **Los datos/logo se borran** → falta el `[mounts]` o el volumen no quedó attached. Revisa
  pasos 3–4 y `fly volumes list`.
- **SQLite + varias máquinas** → SQLite es de **una sola máquina**. Mantén `fly scale count 1`.

---

## 🔁 Restaurar un respaldo (si algún día pierdes el volumen)

La app tiene un botón **Admin → "⬇️ Descargar copia de la BD"** que baja un `quiniela-backup-*.db`.
Para restaurarlo dentro del volumen:
```bash
fly sftp shell -a quiniela-interna-rpci
# dentro del shell sftp:
put quiniela-backup-XXXX.db /app/instance/quiniela.db
# salir y reiniciar:
fly apps restart quiniela-interna-rpci
```

---

## Notas de costo
- Volumen de 1 GB ≈ **$0.15/mes**. Es el mínimo; no se puede crear más pequeño.
- Con `auto_stop_machines = 'stop'` la máquina duerme y casi no cobra compute.
- Atiende los correos de **pago fallido** de Fly: impago prolongado → suspensión → posible
  borrado del volumen (perderías la BD si no tienes backup).
