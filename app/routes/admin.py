import os
import uuid
import sqlite3
import tempfile
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
    send_file,
)
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

from ..models import db, Usuario, Match, Participante, Ajustes
from ..services import generar_matches, reset_matches, borrar_usuarios, polla_lista
from ..auth import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# --------------------------------------------------------------------------- #
# Autenticación
# --------------------------------------------------------------------------- #
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if password == current_app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            flash("Sesión iniciada.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Contraseña incorrecta.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("is_admin", None)
    flash("Sesión cerrada.", "info")
    return redirect(url_for("polla.index"))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@admin_bp.route("/")
@admin_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        n_usuarios=Usuario.query.count(),
        n_participantes=Participante.query.count(),
        n_disponibles=Match.query.filter_by(disponible=True).count(),
        n_matches=Match.query.count(),
        lista=polla_lista(),
    )


# --------------------------------------------------------------------------- #
# Respaldo: descargar la base de datos completa
# --------------------------------------------------------------------------- #
@admin_bp.route("/backup")
@admin_required
def backup():
    """Descarga una copia consistente de la BD SQLite (sirve como respaldo).

    Usa 'VACUUM INTO' para obtener una foto coherente aunque esté en modo WAL,
    y no depende de flyctl ni de acceso externo: la app se respalda a sí misma.
    """
    db_path = db.engine.url.database
    if not db_path or not os.path.exists(db_path):
        flash("No se encontró el archivo de base de datos.", "error")
        return redirect(url_for("admin.dashboard"))

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.remove(tmp.name)  # VACUUM INTO exige que el destino NO exista

    con = sqlite3.connect(db_path)
    try:
        con.execute("VACUUM INTO ?", (tmp.name,))
    finally:
        con.close()

    fecha = datetime.now().strftime("%Y%m%d-%H%M")
    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f"quiniela-backup-{fecha}.db",
        mimetype="application/octet-stream",
    )


# --------------------------------------------------------------------------- #
# CRUD Usuarios
# --------------------------------------------------------------------------- #
@admin_bp.route("/usuarios")
@admin_required
def usuarios():
    return render_template(
        "admin/usuarios.html",
        usuarios=Usuario.query.order_by(Usuario.nombre_usuario).all(),
    )


def _duplicado(nombre, id_usuario, excluir_id=None):
    """Devuelve un mensaje si el nombre (ignorando mayúsculas) o el ID ya existen."""
    q_nombre = Usuario.query.filter(
        db.func.lower(Usuario.nombre_usuario) == nombre.lower()
    )
    q_id = Usuario.query.filter(Usuario.id_usuario == id_usuario)
    if excluir_id is not None:
        q_nombre = q_nombre.filter(Usuario.id != excluir_id)
        q_id = q_id.filter(Usuario.id != excluir_id)

    if db.session.query(q_nombre.exists()).scalar():
        return "Ya existe un usuario con ese nombre."
    if db.session.query(q_id.exists()).scalar():
        return "Ya existe un usuario con ese ID."
    return None


@admin_bp.route("/usuarios/crear", methods=["POST"])
@admin_required
def usuarios_crear():
    # Normaliza el nombre: sin espacios sobrantes ni dobles espacios internos.
    nombre = " ".join((request.form.get("nombre_usuario") or "").split())
    id_usuario = (request.form.get("id_usuario") or "").strip()

    if not nombre or not id_usuario:
        flash("Nombre e ID son obligatorios.", "error")
        return redirect(url_for("admin.usuarios"))

    error = _duplicado(nombre, id_usuario)
    if error:
        flash(error, "error")
        return redirect(url_for("admin.usuarios"))

    db.session.add(Usuario(nombre_usuario=nombre, id_usuario=id_usuario))
    try:
        db.session.commit()
        flash("Usuario creado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Ya existe un usuario con ese nombre o ID.", "error")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/<int:uid>/editar", methods=["POST"])
@admin_required
def usuarios_editar(uid):
    usuario = Usuario.query.get_or_404(uid)
    nombre = " ".join((request.form.get("nombre_usuario") or "").split())
    id_usuario = (request.form.get("id_usuario") or "").strip()

    if not nombre or not id_usuario:
        flash("Nombre e ID son obligatorios.", "error")
        return redirect(url_for("admin.usuarios"))

    error = _duplicado(nombre, id_usuario, excluir_id=usuario.id)
    if error:
        flash(error, "error")
        return redirect(url_for("admin.usuarios"))

    usuario.nombre_usuario = nombre
    usuario.id_usuario = id_usuario
    try:
        db.session.commit()
        flash("Usuario actualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Ya existe un usuario con ese nombre o ID.", "error")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/borrar-todo", methods=["GET", "POST"])
@admin_required
def usuarios_borrar_todo():
    if request.method == "POST":
        confirmacion = (request.form.get("confirmacion") or "").strip()
        if confirmacion != "BORRAR":
            flash('Debes escribir exactamente "BORRAR" para confirmar.', "error")
            return redirect(url_for("admin.usuarios_borrar_todo"))
        borrar_usuarios()
        flash("Todos los usuarios fueron eliminados.", "success")
        return redirect(url_for("admin.usuarios"))

    return render_template(
        "admin/usuarios_reset_confirm.html", n_usuarios=Usuario.query.count()
    )


@admin_bp.route("/usuarios/<int:uid>/eliminar", methods=["POST"])
@admin_required
def usuarios_eliminar(uid):
    usuario = Usuario.query.get_or_404(uid)
    # Si estaba participando y tenía marcador, liberamos el marcador.
    if usuario.participante and usuario.participante.match:
        usuario.participante.match.disponible = True
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuario eliminado.", "success")
    return redirect(url_for("admin.usuarios"))


# --------------------------------------------------------------------------- #
# Participantes (selección desde Usuarios)
# --------------------------------------------------------------------------- #
@admin_bp.route("/participantes", methods=["GET", "POST"])
@admin_required
def participantes():
    if request.method == "POST":
        seleccionados = set(request.form.getlist("usuario_ids", type=int))
        actuales = {p.usuario_id: p for p in Participante.query.all()}

        # Altas.
        for uid in seleccionados - set(actuales):
            db.session.add(Participante(usuario_id=uid))

        # Bajas: nunca quitamos a quien ya tiene marcador asignado
        # (su checkbox llega deshabilitado y por eso no se envía).
        for uid in set(actuales) - seleccionados:
            p = actuales[uid]
            if p.match_id is not None:
                continue
            db.session.delete(p)

        db.session.commit()
        flash("Participantes actualizados.", "success")
        return redirect(url_for("admin.participantes"))

    return render_template(
        "admin/participantes.html",
        usuarios=Usuario.query.order_by(Usuario.nombre_usuario).all(),
    )


# --------------------------------------------------------------------------- #
# Ajustes + generación de Match
# --------------------------------------------------------------------------- #
def _guardar_logo(file, ajustes):
    if not file or not file.filename:
        return
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        flash("Formato de logo no permitido.", "error")
        return
    nombre = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], secure_filename(nombre)))
    # Borra el logo anterior si existía.
    if ajustes.logo_filename:
        anterior = os.path.join(
            current_app.config["UPLOAD_FOLDER"], ajustes.logo_filename
        )
        if os.path.exists(anterior):
            os.remove(anterior)
    ajustes.logo_filename = nombre


@admin_bp.route("/ajustes", methods=["GET", "POST"])
@admin_required
def ajustes():
    ajustes = Ajustes.get()

    if request.method == "POST":
        ajustes.titulo_quiniela = (
            request.form.get("titulo_quiniela") or ajustes.titulo_quiniela
        ).strip()
        ajustes.equipo_local = (request.form.get("equipo_local") or "Local").strip()
        ajustes.equipo_visitante = (
            request.form.get("equipo_visitante") or "Visitante"
        ).strip()
        ajustes.max_local = request.form.get("max_local", type=int) or 0
        ajustes.max_visitante = request.form.get("max_visitante", type=int) or 0
        ajustes.max_global = request.form.get("max_global", type=int) or 0

        _guardar_logo(request.files.get("logo"), ajustes)

        db.session.commit()
        flash("Ajustes guardados.", "success")
        return redirect(url_for("admin.ajustes"))

    return render_template("admin/ajustes.html", ajustes=ajustes)


@admin_bp.route("/ajustes/generar", methods=["POST"])
@admin_required
def generar():
    ajustes = Ajustes.get()
    creados, error = generar_matches(ajustes)
    if error:
        flash(error, "error")
    else:
        flash(f"Se generaron {creados} marcadores.", "success")
    return redirect(url_for("admin.match"))


# --------------------------------------------------------------------------- #
# Tabla Match + reset con doble validación
# --------------------------------------------------------------------------- #
@admin_bp.route("/match")
@admin_required
def match():
    matches = Match.query.order_by(Match.goles_local, Match.goles_visitante).all()
    return render_template("admin/match.html", matches=matches)


@admin_bp.route("/match/reset", methods=["GET", "POST"])
@admin_required
def match_reset():
    if request.method == "POST":
        confirmacion = (request.form.get("confirmacion") or "").strip()
        if confirmacion != "BORRAR":
            flash('Debes escribir exactamente "BORRAR" para confirmar.', "error")
            return redirect(url_for("admin.match_reset"))
        reset_matches()
        flash("Tabla Match reseteada.", "success")
        return redirect(url_for("admin.match"))

    return render_template("admin/reset_confirm.html")
