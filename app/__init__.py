import os

from flask import Flask

from .models import db, Ajustes


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object("config.Config")

    # Asegura carpetas necesarias (SQLite y logos subidos).
    os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    from .routes.polla import polla_bp
    from .routes.admin import admin_bp

    app.register_blueprint(polla_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        Ajustes.get()  # crea el singleton de ajustes si no existe

    return app
