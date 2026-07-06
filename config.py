import os

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, "instance")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-please")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(instance_dir, "quiniela.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Contraseña única para el panel de administración.
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    # Subida de logo del banner.
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
