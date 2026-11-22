"""Reglas de negocio de Pit Wall.

Toda escritura a la base de datos pasa por este módulo, para que las reglas de negocio RN-### (documentadas en
docs/Documentacion.md) se cumplan sin importar desde dónde se llame (interfaz web o pruebas).
"""
import sqlite3
from datetime import date

# RN-001: puntos del 1.º al 10.º lugar; del 11.º en adelante y los abandonos no suman.
PUNTOS = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)
MAX_PILOTOS_POR_ESCUDERIA = 2  # RN-002
NUMERO_MIN, NUMERO_MAX = 1, 99  # RN-003


class ReglaNegocioError(Exception):
    """Se lanza cuando una operación incumple una regla de negocio."""

    def __init__(self, regla: str, mensaje: str):
        super().__init__(f"{regla}: {mensaje}")
        self.regla = regla
        self.mensaje = mensaje


class DatoInvalido(ValueError):
    """Dato vacío o con formato incorrecto (no es una regla de negocio)."""


def _texto(valor: str, campo: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise DatoInvalido(f"El campo «{campo}» es obligatorio.")
    return valor


def _entero(valor, campo: str) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise DatoInvalido(f"El campo «{campo}» debe ser un número entero.") from None


# ---------------------------------------------------------------- RN-001 Puntuación
def puntos_por_posicion(posicion: int | None, abandono: bool) -> int:
    if abandono or posicion is None or posicion < 1 or posicion > len(PUNTOS):
        return 0
    return PUNTOS[posicion - 1]


# ---------------------------------------------------------------- Escuderías
def crear_escuderia(conn: sqlite3.Connection, nombre: str, pais: str) -> int:
    nombre, pais = _texto(nombre, "Nombre"), _texto(pais, "País")
    if conn.execute("SELECT 1 FROM escuderias WHERE lower(nombre) = lower(?)", (nombre,)).fetchone():
        raise DatoInvalido(f"Ya existe la escudería «{nombre}».")
    cur = conn.execute("INSERT INTO escuderias (nombre, pais) VALUES (?, ?)", (nombre, pais))
    conn.commit()
    return cur.lastrowid


def editar_escuderia(conn: sqlite3.Connection, escuderia_id: int, nombre: str, pais: str) -> None:
    nombre, pais = _texto(nombre, "Nombre"), _texto(pais, "País")
    otra = conn.execute("SELECT id FROM escuderias WHERE lower(nombre) = lower(?) AND id <> ?", (nombre, escuderia_id)).fetchone()
    if otra:
        raise DatoInvalido(f"Ya existe la escudería «{nombre}».")
    conn.execute("UPDATE escuderias SET nombre = ?, pais = ? WHERE id = ?", (nombre, pais, escuderia_id))
    conn.commit()


def eliminar_escuderia(conn: sqlite3.Connection, escuderia_id: int) -> None:
    # RN-006: no se borra lo que tiene historial asociado.
    pilotos = conn.execute("SELECT COUNT(*) FROM pilotos WHERE escuderia_id = ?", (escuderia_id,)).fetchone()[0]
    if pilotos:
        raise ReglaNegocioError("RN-006", f"La escudería tiene {pilotos} piloto(s); primero cámbialos de escudería o elimínalos.")
    conn.execute("DELETE FROM escuderias WHERE id = ?", (escuderia_id,))
    conn.commit()


# ---------------------------------------------------------------- Pilotos
def _validar_piloto(conn, numero, escuderia_id, piloto_id=None) -> tuple[int, int]:
    numero = _entero(numero, "Número")
    escuderia_id = _entero(escuderia_id, "Escudería")
    # RN-003: número entre 1 y 99 y único en la parrilla.
    if not NUMERO_MIN <= numero <= NUMERO_MAX:
        raise ReglaNegocioError("RN-003", f"El número de piloto debe estar entre {NUMERO_MIN} y {NUMERO_MAX}.")
    dueño = conn.execute("SELECT nombre FROM pilotos WHERE numero = ? AND id IS NOT ?", (numero, piloto_id)).fetchone()
    if dueño:
        raise ReglaNegocioError("RN-003", f"El número {numero} ya lo usa {dueño['nombre']}.")
    if not conn.execute("SELECT 1 FROM escuderias WHERE id = ?", (escuderia_id,)).fetchone():
        raise DatoInvalido("La escudería elegida no existe.")
    # RN-002: máximo dos pilotos por escudería.
    ocupados = conn.execute(
        "SELECT COUNT(*) FROM pilotos WHERE escuderia_id = ? AND id IS NOT ?", (escuderia_id, piloto_id)
    ).fetchone()[0]
    if ocupados >= MAX_PILOTOS_POR_ESCUDERIA:
        raise ReglaNegocioError("RN-002", f"La escudería ya tiene {MAX_PILOTOS_POR_ESCUDERIA} pilotos.")
    return numero, escuderia_id


def crear_piloto(conn: sqlite3.Connection, nombre: str, numero, nacionalidad: str, escuderia_id) -> int:
    nombre, nacionalidad = _texto(nombre, "Nombre"), _texto(nacionalidad, "Nacionalidad")
    numero, escuderia_id = _validar_piloto(conn, numero, escuderia_id)
    cur = conn.execute(
        "INSERT INTO pilotos (nombre, numero, nacionalidad, escuderia_id) VALUES (?, ?, ?, ?)",
        (nombre, numero, nacionalidad, escuderia_id),
    )
    conn.commit()
    return cur.lastrowid


def editar_piloto(conn: sqlite3.Connection, piloto_id: int, nombre: str, numero, nacionalidad: str, escuderia_id) -> None:
    nombre, nacionalidad = _texto(nombre, "Nombre"), _texto(nacionalidad, "Nacionalidad")
    numero, escuderia_id = _validar_piloto(conn, numero, escuderia_id, piloto_id)
    conn.execute(
        "UPDATE pilotos SET nombre = ?, numero = ?, nacionalidad = ?, escuderia_id = ? WHERE id = ?",
        (nombre, numero, nacionalidad, escuderia_id, piloto_id),
    )
    conn.commit()


def eliminar_piloto(conn: sqlite3.Connection, piloto_id: int) -> None:
    # RN-006: un piloto con resultados forma parte del campeonato.
    n = conn.execute("SELECT COUNT(*) FROM resultados WHERE piloto_id = ?", (piloto_id,)).fetchone()[0]
    if n:
        raise ReglaNegocioError("RN-006", f"El piloto tiene {n} resultado(s) registrados; no se puede eliminar.")
    conn.execute("DELETE FROM pilotos WHERE id = ?", (piloto_id,))
    conn.commit()


# ---------------------------------------------------------------- Carreras
def _fecha(valor: str) -> str:
    try:
        return date.fromisoformat(_texto(valor, "Fecha")).isoformat()
    except ValueError:
        raise DatoInvalido("La fecha debe tener el formato AAAA-MM-DD.") from None


def crear_carrera(conn: sqlite3.Connection, ronda, nombre: str, circuito: str, fecha: str) -> int:
    ronda = _entero(ronda, "Ronda")
    nombre, circuito, fecha = _texto(nombre, "Nombre"), _texto(circuito, "Circuito"), _fecha(fecha)
    if conn.execute("SELECT 1 FROM carreras WHERE ronda = ?", (ronda,)).fetchone():
        raise DatoInvalido(f"Ya existe la ronda {ronda}.")
    cur = conn.execute(
        "INSERT INTO carreras (ronda, nombre, circuito, fecha) VALUES (?, ?, ?, ?)", (ronda, nombre, circuito, fecha)
    )
    conn.commit()
    return cur.lastrowid


def editar_carrera(conn: sqlite3.Connection, carrera_id: int, ronda, nombre: str, circuito: str, fecha: str) -> None:
    ronda = _entero(ronda, "Ronda")
    nombre, circuito, fecha = _texto(nombre, "Nombre"), _texto(circuito, "Circuito"), _fecha(fecha)
    if conn.execute("SELECT 1 FROM carreras WHERE ronda = ? AND id <> ?", (ronda, carrera_id)).fetchone():
        raise DatoInvalido(f"Ya existe la ronda {ronda}.")
    tiene = conn.execute("SELECT 1 FROM resultados WHERE carrera_id = ?", (carrera_id,)).fetchone()
    if tiene and date.fromisoformat(fecha) > date.today():
        raise ReglaNegocioError("RN-005", "La carrera ya tiene resultados; su fecha no puede pasar al futuro.")
    conn.execute(
        "UPDATE carreras SET ronda = ?, nombre = ?, circuito = ?, fecha = ? WHERE id = ?",
        (ronda, nombre, circuito, fecha, carrera_id),
    )
    conn.commit()


def eliminar_carrera(conn: sqlite3.Connection, carrera_id: int) -> None:
    conn.execute("DELETE FROM carreras WHERE id = ?", (carrera_id,))
    conn.commit()


# ---------------------------------------------------------------- Resultados
def registrar_resultados(conn: sqlite3.Connection, carrera_id: int, filas: list[tuple], hoy: date | None = None) -> None:
    """Reemplaza los resultados de una carrera.

    filas: lista de (piloto_id, posición o None, abandono). Un piloto sin posición y sin abandono no corrió.
    """
    hoy = hoy or date.today()
    carrera = conn.execute("SELECT fecha FROM carreras WHERE id = ?", (carrera_id,)).fetchone()
    if carrera is None:
        raise DatoInvalido("La carrera no existe.")
    # RN-005: solo se registran resultados de carreras que ya se corrieron.
    if date.fromisoformat(carrera["fecha"]) > hoy:
        raise ReglaNegocioError("RN-005", f"La carrera es el {carrera['fecha']}; todavía no se corre.")

    vistos_pilotos, vistas_posiciones, limpias = set(), set(), []
    for piloto_id, posicion, abandono in filas:
        abandono = bool(abandono)
        posicion = None if abandono or posicion in (None, "") else _entero(posicion, "Posición")
        if posicion is None and not abandono:
            continue
        # RN-004: un resultado por piloto y una posición por piloto.
        if piloto_id in vistos_pilotos:
            raise ReglaNegocioError("RN-004", "Un piloto no puede tener dos resultados en la misma carrera.")
        if posicion is not None:
            if posicion < 1:
                raise DatoInvalido("La posición debe ser 1 o mayor.")
            if posicion in vistas_posiciones:
                raise ReglaNegocioError("RN-004", f"La posición {posicion} está asignada a más de un piloto.")
            vistas_posiciones.add(posicion)
        vistos_pilotos.add(piloto_id)
        limpias.append((piloto_id, posicion, abandono))

    if vistas_posiciones and sorted(vistas_posiciones) != list(range(1, len(vistas_posiciones) + 1)):
        raise ReglaNegocioError("RN-004", "Las posiciones deben ser consecutivas desde el 1.º lugar, sin huecos.")

    with conn:
        conn.execute("DELETE FROM resultados WHERE carrera_id = ?", (carrera_id,))
        conn.executemany(
            "INSERT INTO resultados (carrera_id, piloto_id, posicion, abandono, puntos) VALUES (?, ?, ?, ?, ?)",
            [(carrera_id, p, pos, int(ab), puntos_por_posicion(pos, ab)) for p, pos, ab in limpias],
        )


# ---------------------------------------------------------------- Campeonatos (RN-007)
def campeonato_pilotos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Ordena por puntos; en empate gana quien tenga más victorias, luego más segundos lugares."""
    return conn.execute(
        """
        SELECT p.id, p.nombre, p.numero, p.nacionalidad, e.nombre AS escuderia,
               COALESCE(SUM(r.puntos), 0)                         AS puntos,
               COALESCE(SUM(CASE WHEN r.posicion = 1 THEN 1 END), 0) AS victorias,
               COALESCE(SUM(CASE WHEN r.posicion = 2 THEN 1 END), 0) AS segundos,
               COUNT(r.id)                                        AS carreras
        FROM pilotos p
        JOIN escuderias e ON e.id = p.escuderia_id
        LEFT JOIN resultados r ON r.piloto_id = p.id
        GROUP BY p.id
        ORDER BY puntos DESC, victorias DESC, segundos DESC, p.nombre
        """
    ).fetchall()


def campeonato_constructores(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.id, e.nombre, e.pais,
               COALESCE(SUM(r.puntos), 0)                         AS puntos,
               COALESCE(SUM(CASE WHEN r.posicion = 1 THEN 1 END), 0) AS victorias
        FROM escuderias e
        LEFT JOIN pilotos p ON p.escuderia_id = e.id
        LEFT JOIN resultados r ON r.piloto_id = p.id
        GROUP BY e.id
        ORDER BY puntos DESC, victorias DESC, e.nombre
        """
    ).fetchall()
