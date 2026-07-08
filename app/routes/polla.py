from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_from_directory,
    current_app,
)

from ..models import db, Match, Participante, Ajustes
from ..services import asignar_marcador, polla_lista

polla_bp = Blueprint("polla", __name__)


@polla_bp.route("/media/<path:filename>")
def media(filename):
    """Sirve archivos subidos (ej. el logo) desde el volumen persistente."""
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@polla_bp.route("/estado")
def estado():
    """Estado ligero para el sondeo del navegador (redirección remota)."""
    ajustes = Ajustes.get()
    return jsonify(redirect=ajustes.redirect_url or None)


@polla_bp.route("/")
def index():
    ajustes = Ajustes.get()
    # Interruptor del admin: si hay URL de redirección, se envía a todos allí.
    if ajustes.redirect_url:
        return redirect(ajustes.redirect_url)
    participantes = (
        Participante.query.join(Participante.usuario)
        .order_by(Participante.match_id.isnot(None).desc())
        .all()
    )
    disponibles = (
        Match.query.filter_by(disponible=True)
        .order_by(Match.goles_local, Match.goles_visitante)
        .all()
    )
    pendientes = [p for p in participantes if not p.asignado]
    asignados = [p for p in participantes if p.asignado]

    return render_template(
        "polla.html",
        ajustes=ajustes,
        asignados=asignados,
        pendientes=pendientes,
        disponibles=disponibles,
        lista=polla_lista(),
    )


def _wants_json():
    """La ruleta llama por fetch con este header; entonces respondemos JSON."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@polla_bp.route("/asignar", methods=["POST"])
def asignar():
    wants_json = _wants_json()

    def fail(msg):
        if wants_json:
            return jsonify(ok=False, error=msg)
        flash(msg, "popup")
        return redirect(url_for("polla.index"))

    participante_id = request.form.get("participante_id", type=int)
    digitos = (request.form.get("digitos") or "").strip()

    participante = Participante.query.get(participante_id) if participante_id else None

    if participante is None:
        return fail("Selecciona un participante pendiente.")

    if participante.asignado:
        return fail("Ese participante ya tiene un marcador asignado.")

    # Validación: 3 últimos dígitos del ID del usuario, con mensajes claros.
    if not digitos:
        return fail("Debes escribir los 3 últimos dígitos de tu ID antes de asignar.")

    if not digitos.isdigit() or len(digitos) != 3:
        return fail("Escribe exactamente 3 dígitos numéricos (por ejemplo: 123).")

    id_real = "".join(ch for ch in participante.usuario.id_usuario if ch.isdigit())
    if id_real[-3:] != digitos:
        return fail(
            "Ese número no corresponde a este participante. "
            "Recuerda que son los últimos 3 dígitos de tu ID; verifícalos e inténtalo de nuevo."
        )

    match = asignar_marcador(participante)
    if match is None:
        return fail("¡Ya no quedan marcadores disponibles!")

    if wants_json:
        return jsonify(
            ok=True,
            nombre=participante.usuario.nombre_usuario,
            goles_local=match.goles_local,
            goles_visitante=match.goles_visitante,
        )

    flash(
        f"{participante.usuario.nombre_usuario}: marcador asignado {match.marcador}.",
        "success",
    )
    return redirect(url_for("polla.index"))
