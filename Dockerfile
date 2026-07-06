FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Directorios persistentes (SQLite y logos subidos).
# Se corre como root (por defecto) para poder escribir el Volume de Fly, que se
# monta como root; en la microVM aislada de Fly esto es estándar y seguro. El
# named volume de Docker local también funciona sin problema de permisos.
RUN mkdir -p /app/instance /app/app/static/uploads

EXPOSE 8000

# 2 workers x 8 hilos = 16 peticiones concurrentes (ideal para ráfagas), poca RAM.
CMD ["gunicorn", "-w", "2", "--threads", "8", "-k", "gthread", "--timeout", "60", \
     "-b", "0.0.0.0:8000", "--access-logfile", "-", "wsgi:app"]
