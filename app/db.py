"""Conexión a SQLite, creación de tablas y datos de ejemplo."""
import sqlite3

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
    escuderia_id  INTEGER NOT NULL REFERENCES escuderias(id)
);
CREATE TABLE IF NOT EXISTS carreras (
    id        INTEGER PRIMARY KEY,
    ronda     INTEGER NOT NULL UNIQUE,
    nombre    TEXT NOT NULL,
    circuito  TEXT NOT NULL,
    fecha     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resultados (
    id          INTEGER PRIMARY KEY,
    carrera_id  INTEGER NOT NULL REFERENCES carreras(id) ON DELETE CASCADE,
    piloto_id   INTEGER NOT NULL REFERENCES pilotos(id),
    posicion    INTEGER,
    abandono    INTEGER NOT NULL DEFAULT 0,
    puntos      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (carrera_id, piloto_id),
    UNIQUE (carrera_id, posicion)
);
"""

# Datos de ejemplo: escuderías y pilotos de la temporada 2024 y el resultado real del GP de Baréin 2024.
ESCUDERIAS = [
    ("Red Bull Racing", "Austria"),
    ("Ferrari", "Italia"),
    ("Mercedes", "Alemania"),
    ("McLaren", "Reino Unido"),
    ("Aston Martin", "Reino Unido"),
]
PILOTOS = [  # (nombre, número, nacionalidad, escudería)
    ("Max Verstappen", 1, "Países Bajos", "Red Bull Racing"),
    ("Sergio Pérez", 11, "México", "Red Bull Racing"),
    ("Charles Leclerc", 16, "Mónaco", "Ferrari"),
    ("Carlos Sainz", 55, "España", "Ferrari"),
    ("Lewis Hamilton", 44, "Reino Unido", "Mercedes"),
    ("George Russell", 63, "Reino Unido", "Mercedes"),
    ("Lando Norris", 4, "Reino Unido", "McLaren"),
    ("Oscar Piastri", 81, "Australia", "McLaren"),
    ("Fernando Alonso", 14, "España", "Aston Martin"),
    ("Lance Stroll", 18, "Canadá", "Aston Martin"),
]
CARRERAS = [  # (ronda, nombre, circuito, fecha)
    (1, "GP de Baréin", "Circuito Internacional de Baréin", "2024-03-02"),
    (2, "GP de Arabia Saudita", "Circuito de la Corniche de Yeda", "2024-03-09"),
    (3, "GP de Australia", "Circuito de Albert Park", "2024-03-24"),
    (4, "GP de Japón", "Circuito de Suzuka", "2024-04-07"),
]
BAREIN_2024 = [1, 11, 55, 16, 63, 4, 44, 81, 14, 18]  # números de piloto del 1.º al 10.º lugar


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
        cargar_ejemplo(conn)
    conn.commit()


def cargar_ejemplo(conn: sqlite3.Connection) -> None:
    from . import reglas

    ids = {nombre: reglas.crear_escuderia(conn, nombre, pais) for nombre, pais in ESCUDERIAS}
    for nombre, numero, nac, esc in PILOTOS:
        reglas.crear_piloto(conn, nombre, numero, nac, ids[esc])
    for ronda, nombre, circuito, fecha in CARRERAS:
        reglas.crear_carrera(conn, ronda, nombre, circuito, fecha)
    por_numero = {r["numero"]: r["id"] for r in conn.execute("SELECT id, numero FROM pilotos")}
    filas = [(por_numero[n], pos, False) for pos, n in enumerate(BAREIN_2024, start=1)]
    reglas.registrar_resultados(conn, 1, filas)


def init_app(app: Flask) -> None:
    app.teardown_appcontext(cerrar_db)
    conn = conectar(app.config["DATABASE"])
    try:
        crear_tablas(conn, app.config["DATOS_EJEMPLO"])
    finally:
        conn.close()
