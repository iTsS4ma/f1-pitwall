"""Pit Wall: gestor de una temporada de Fórmula 1."""
import os

from flask import Flask

from . import db, rutas


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "pitwall-desarrollo"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "pitwall.db")),
        DATOS_EJEMPLO=os.environ.get("DATOS_EJEMPLO", "1") == "1",
    )
    if config:
        app.config.update(config)
    carpeta = os.path.dirname(app.config["DATABASE"])
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)

    db.init_app(app)
    app.register_blueprint(rutas.bp)
    return app
