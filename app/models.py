import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    """SQLite en modo WAL + espera ante bloqueos: mejor concurrencia de lecturas/escrituras.

    - WAL: lecturas y escrituras conviven sin bloquearse entre sí.
    - busy_timeout: si otra escritura tiene el lock, espera hasta 5 s en vez de
      fallar de inmediato con 'database is locked'.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
        cur.close()


class Usuario(db.Model):
    """Lista maestra de personas. No todas participan en la quiniela actual."""

    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    # collation NOCASE => la unicidad ignora mayúsculas/minúsculas.
    nombre_usuario = db.Column(
        db.String(120, collation="NOCASE"), nullable=False, unique=True
    )
    # Se validan sus 3 últimos dígitos al autoasignarse un marcador.
    id_usuario = db.Column(db.String(40), nullable=False, unique=True)

    participante = db.relationship(
        "Participante",
        backref="usuario",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def participa(self):
        return self.participante is not None


class Match(db.Model):
    """Un marcador posible del partido. Ninguna fila completa puede repetirse."""

    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)
    local = db.Column(db.String(80), nullable=False)
    visitante = db.Column(db.String(80), nullable=False)
    goles_local = db.Column(db.Integer, nullable=False)
    goles_visitante = db.Column(db.Integer, nullable=False)
    disponible = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint(
            "local",
            "visitante",
            "goles_local",
            "goles_visitante",
            name="uq_match_row",
        ),
    )

    @property
    def marcador(self):
        return f"{self.goles_local} - {self.goles_visitante}"


class Participante(db.Model):
    """Usuario habilitado para la quiniela actual y su marcador asignado."""

    __tablename__ = "participante"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuario.id"), unique=True, nullable=False
    )
    # unique=True => ningún marcador se repite entre participantes.
    match_id = db.Column(
        db.Integer, db.ForeignKey("match.id"), unique=True, nullable=True
    )

    match = db.relationship("Match")

    @property
    def asignado(self):
        return self.match_id is not None


class Ajustes(db.Model):
    """Configuración singleton de la quiniela actual."""

    __tablename__ = "ajustes"

    id = db.Column(db.Integer, primary_key=True)
    equipo_local = db.Column(db.String(80), nullable=False, default="Local")
    equipo_visitante = db.Column(db.String(80), nullable=False, default="Visitante")
    max_local = db.Column(db.Integer, nullable=False, default=4)
    max_visitante = db.Column(db.Integer, nullable=False, default=4)
    max_global = db.Column(db.Integer, nullable=False, default=8)
    titulo_quiniela = db.Column(db.String(120), nullable=False, default="Quiniela RPCI")
    logo_filename = db.Column(db.String(200), nullable=True)
    # Si tiene una URL, la Polla_View pública redirige a todos los visitantes ahí
    # (interruptor de "cerrar/redirigir" controlado por el admin). None = inactivo.
    redirect_url = db.Column(db.String(300), nullable=True)

    @staticmethod
    def get():
        """Devuelve el registro singleton, creándolo si no existe."""
        ajustes = Ajustes.query.first()
        if ajustes is None:
            ajustes = Ajustes()
            db.session.add(ajustes)
            db.session.commit()
        return ajustes
