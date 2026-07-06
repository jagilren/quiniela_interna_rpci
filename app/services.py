import random

from .models import db, Usuario, Match, Participante, Ajustes


def generar_matches(ajustes):
    """Genera todos los marcadores posibles según los parámetros de goles.

    Recorre de 0-0 hasta max_local x max_visitante, incluyendo solo los
    marcadores cuya suma no supere max_global.

    Requiere la tabla Match vacía (usar reset_matches() antes de regenerar).

    Devuelve (creados:int, error:str|None).
    """
    if Match.query.first() is not None:
        return 0, "Ya existen marcadores. Resetea la tabla Match antes de generar."

    creados = 0
    for gl in range(0, ajustes.max_local + 1):
        for gv in range(0, ajustes.max_visitante + 1):
            if gl + gv <= ajustes.max_global:
                db.session.add(
                    Match(
                        local=ajustes.equipo_local,
                        visitante=ajustes.equipo_visitante,
                        goles_local=gl,
                        goles_visitante=gv,
                        disponible=True,
                    )
                )
                creados += 1

    if creados == 0:
        return 0, "Los parámetros no producen ningún marcador válido."

    db.session.commit()
    return creados, None


def reset_matches():
    """Borra todos los marcadores y limpia las asignaciones de los participantes."""
    Participante.query.update({Participante.match_id: None})
    Match.query.delete()
    db.session.commit()


def borrar_usuarios():
    """Borra TODOS los usuarios (y sus participaciones), liberando sus marcadores.

    La tabla Match se conserva; los marcadores que estaban asignados vuelven a
    quedar disponibles.
    """
    # Libera los marcadores que estaban tomados (disponible=False => asignado).
    Match.query.filter_by(disponible=False).update({Match.disponible: True})
    # Primero las participaciones (por la FK), luego los usuarios.
    Participante.query.delete()
    Usuario.query.delete()
    db.session.commit()


def asignar_marcador(participante):
    """Asigna aleatoriamente un marcador disponible al participante.

    Devuelve el Match asignado, o None si no quedan marcadores disponibles.
    """
    if participante.match_id is not None:
        return participante.match

    disponibles = Match.query.filter_by(disponible=True).all()
    if not disponibles:
        return None

    match = random.choice(disponibles)
    match.disponible = False
    participante.match_id = match.id
    db.session.commit()
    return match


def polla_lista():
    """La Polla_View está lista si hay al menos un participante y marcadores generados."""
    hay_participantes = Participante.query.first() is not None
    hay_matches = Match.query.first() is not None
    return hay_participantes and hay_matches
