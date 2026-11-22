"""Conexión a SQLite, creación de tablas y datos de la temporada 2026."""
import json
import os
import sqlite3
from datetime import date

from flask import Flask, current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS escuderias (
    id      INTEGER PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE,
    pais    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pilotos (
    id            INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL,
    numero        INTEGER NOT NULL UNIQUE,
    nacionalidad  TEXT NOT NULL,
    escuderia_id  INTEGER NOT NULL REFERENCES escuderias(id),
    activo        INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS carreras (
    id                INTEGER PRIMARY KEY,
    ronda             INTEGER NOT NULL UNIQUE,
    nombre            TEXT NOT NULL,
    circuito          TEXT NOT NULL,
    pais              TEXT NOT NULL,
    fecha             TEXT NOT NULL,
    sprint            INTEGER NOT NULL DEFAULT 0,
    distancia         TEXT NOT NULL DEFAULT '75',
    distancia_sprint  TEXT NOT NULL DEFAULT '50'
);
CREATE TABLE IF NOT EXISTS resultados (
    id            INTEGER PRIMARY KEY,
    carrera_id    INTEGER NOT NULL REFERENCES carreras(id) ON DELETE CASCADE,
    sesion        TEXT NOT NULL CHECK (sesion IN ('carrera', 'sprint')),
    piloto_id     INTEGER NOT NULL REFERENCES pilotos(id),
    escuderia_id  INTEGER NOT NULL REFERENCES escuderias(id),
    posicion      INTEGER,
    estado        TEXT NOT NULL,
    puntos        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (carrera_id, sesion, piloto_id),
    UNIQUE (carrera_id, sesion, posicion)
);
"""

# Temporada 2026 real: escuderías, pilotos, calendario y resultados de carreras y sprints.
# Fuente: Jolpica F1 API (antes Ergast), consultada el 21 de noviembre de 2026.
DATOS = os.path.join(os.path.dirname(__file__), "datos_2026.json")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = conectar(current_app.config["DATABASE"])
    return g.db


def conectar(ruta: str) -> sqlite3.Connection:
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def cerrar_db(_error=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def crear_tablas(conn: sqlite3.Connection, datos_ejemplo: bool = True) -> None:
    conn.executescript(ESQUEMA)
    vacia = conn.execute("SELECT COUNT(*) FROM escuderias").fetchone()[0] == 0
    if datos_ejemplo and vacia:
        cargar_temporada(conn)
    conn.commit()


def cargar_temporada(conn: sqlite3.Connection, hoy: date | None = None) -> None:
    """Carga la temporada 2026 pasando por las mismas reglas que la interfaz."""
    from . import reglas

    with open(DATOS, encoding="utf-8") as f:
        datos = json.load(f)
    ultima = max((c for c in datos["carreras"] if c["resultados"]), key=lambda c: c["ronda"])
    activos = {r["piloto"] for r in ultima["resultados"]}

    esc = {e["id"]: reglas.crear_escuderia(conn, e["nombre"], e["pais"]) for e in datos["escuderias"]}
    pil = {
        p["id"]: reglas.crear_piloto(conn, p["nombre"], p["numero"], p["nacionalidad"], esc[p["escuderia"]], p["id"] in activos)
        for p in datos["pilotos"]
    }
    for c in datos["carreras"]:
        cid = reglas.crear_carrera(conn, c["ronda"], c["nombre"], c["circuito"], c["pais"], c["fecha"], c["sprint"])
        for sesion, clave, distancia in ((reglas.SPRINT, "sprint_resultados", "50"), (reglas.CARRERA, "resultados", "75")):
            if c[clave]:
                filas = [(pil[r["piloto"]], r["posicion"], r["estado"], esc[r["escuderia"]]) for r in c[clave]]
                reglas.registrar_resultados(conn, cid, sesion, distancia, filas, hoy)


def init_app(app: Flask) -> None:
    app.teardown_appcontext(cerrar_db)
    conn = conectar(app.config["DATABASE"])
    try:
        crear_tablas(conn, app.config["DATOS_EJEMPLO"])
    finally:
        conn.close()
