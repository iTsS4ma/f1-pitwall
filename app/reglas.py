"""Reglas de negocio de Pit Wall F1.

Toda escritura a la base de datos pasa por este módulo, para que las reglas de negocio
(documentadas en docs/Documentacion.md) se cumplan sin importar desde dónde se llame.
Los criterios de puntuación y desempate siguen el reglamento 2026 de la FIA
(Sección A, artículos A2.1.3, A2.1.4 y A2.2; Sección B, artículo B1.7.1).
"""
import sqlite3
from collections import Counter
from datetime import date

CARRERA, SPRINT = "carrera", "sprint"

# Puntos de carrera según la distancia que completó el líder (columnas 1 a 4 del artículo A2.2.1).
DISTANCIAS_CARRERA = {
    "menos2": ("Menos de 2 vueltas", ()),
    "2v": ("2 vueltas o más (menos del 25 %)", (6, 4, 3, 2, 1)),
    "25": ("25 % o más (menos del 50 %)", (13, 10, 8, 6, 5, 4, 3, 2, 1)),
    "50": ("50 % o más (menos del 75 %)", (19, 14, 12, 10, 8, 6, 4, 3, 2, 1)),
    "75": ("75 % o más (distancia completa)", (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)),
}
# Puntos de sprint (artículo A2.2.2): solo si el líder completó al menos el 50 %.
DISTANCIAS_SPRINT = {
    "menos50": ("Menos del 50 %", ()),
    "50": ("50 % o más", (8, 7, 6, 5, 4, 3, 2, 1)),
}
CLASIFICADO = "Clasificado"
ESTADOS_SIN_POSICION = ("Abandono", "No salió", "Descalificado", "No clasificado")
AUTOS_POR_ESCUDERIA = 2  # A2.1.3
PILOTOS_POR_TEMPORADA = 4  # B1.7.1
NUMERO_MIN, NUMERO_MAX = 1, 99


class ReglaNegocioError(Exception):
    """Se lanza cuando una operación incumple una regla de negocio."""

    def __init__(self, regla: str, mensaje: str):
        super().__init__(mensaje)
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


# ---------------------------------------------------------------- Puntuación
def tabla_puntos(sesion: str, distancia: str) -> tuple:
    tablas = DISTANCIAS_CARRERA if sesion == CARRERA else DISTANCIAS_SPRINT
    if distancia not in tablas:
        raise DatoInvalido("La distancia completada no es válida.")
    return tablas[distancia][1]


def puntos(sesion: str, distancia: str, posicion: int | None, estado: str = CLASIFICADO) -> int:
    """RN-001, RN-002 y RN-003: puntos de un resultado."""
    tabla = tabla_puntos(sesion, distancia)
    if estado != CLASIFICADO or posicion is None or not 1 <= posicion <= len(tabla):
        return 0
    return tabla[posicion - 1]


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
    if conn.execute("SELECT 1 FROM escuderias WHERE lower(nombre) = lower(?) AND id <> ?", (nombre, escuderia_id)).fetchone():
        raise DatoInvalido(f"Ya existe la escudería «{nombre}».")
    conn.execute("UPDATE escuderias SET nombre = ?, pais = ? WHERE id = ?", (nombre, pais, escuderia_id))
    conn.commit()


def eliminar_escuderia(conn: sqlite3.Connection, escuderia_id: int) -> None:
    # RN-011: no se borra lo que tiene historial.
    pilotos = conn.execute("SELECT COUNT(*) FROM pilotos WHERE escuderia_id = ?", (escuderia_id,)).fetchone()[0]
    if pilotos:
        raise ReglaNegocioError("RN-011", f"La escudería tiene {pilotos} piloto(s); primero cámbialos de escudería o elimínalos.")
    if conn.execute("SELECT 1 FROM resultados WHERE escuderia_id = ?", (escuderia_id,)).fetchone():
        raise ReglaNegocioError("RN-011", "La escudería tiene resultados en la temporada; no se puede eliminar.")
    conn.execute("DELETE FROM escuderias WHERE id = ?", (escuderia_id,))
    conn.commit()


# ---------------------------------------------------------------- Pilotos
def _pilotos_de_temporada(conn, escuderia_id) -> set:
    """Pilotos que ya corrieron con la escudería o que hoy están en ella."""
    filas = conn.execute(
        "SELECT piloto_id FROM resultados WHERE escuderia_id = ? UNION SELECT id FROM pilotos WHERE escuderia_id = ?",
        (escuderia_id, escuderia_id),
    ).fetchall()
    return {f[0] for f in filas}


def _validar_piloto(conn, numero, escuderia_id, activo: bool, piloto_id=None) -> tuple[int, int]:
    numero = _entero(numero, "Número")
    escuderia_id = _entero(escuderia_id, "Escudería")
    # RN-006: número entre 1 y 99 y único en la parrilla.
    if not NUMERO_MIN <= numero <= NUMERO_MAX:
        raise ReglaNegocioError("RN-006", f"El número de piloto debe estar entre {NUMERO_MIN} y {NUMERO_MAX}.")
    dueño = conn.execute("SELECT nombre FROM pilotos WHERE numero = ? AND id IS NOT ?", (numero, piloto_id)).fetchone()
    if dueño:
        raise ReglaNegocioError("RN-006", f"El número {numero} ya lo usa {dueño['nombre']}.")
    if not conn.execute("SELECT 1 FROM escuderias WHERE id = ?", (escuderia_id,)).fetchone():
        raise DatoInvalido("La escudería elegida no existe.")
    # RN-004: cada escudería tiene dos autos, así que como máximo dos pilotos activos.
    if activo:
        activos = conn.execute(
            "SELECT COUNT(*) FROM pilotos WHERE escuderia_id = ? AND activo = 1 AND id IS NOT ?", (escuderia_id, piloto_id)
        ).fetchone()[0]
        if activos >= AUTOS_POR_ESCUDERIA:
            raise ReglaNegocioError("RN-004", f"La escudería ya tiene {AUTOS_POR_ESCUDERIA} pilotos activos; marca a este piloto como reserva.")
    # RN-005: máximo cuatro pilotos distintos por escudería en la temporada.
    usados = _pilotos_de_temporada(conn, escuderia_id) - {piloto_id}
    if len(usados) >= PILOTOS_POR_TEMPORADA:
        raise ReglaNegocioError("RN-005", f"La escudería ya usó {PILOTOS_POR_TEMPORADA} pilotos distintos esta temporada.")
    return numero, escuderia_id


def crear_piloto(conn: sqlite3.Connection, nombre: str, numero, nacionalidad: str, escuderia_id, activo: bool = True) -> int:
    nombre, nacionalidad = _texto(nombre, "Nombre"), _texto(nacionalidad, "Nacionalidad")
    numero, escuderia_id = _validar_piloto(conn, numero, escuderia_id, activo)
    cur = conn.execute(
        "INSERT INTO pilotos (nombre, numero, nacionalidad, escuderia_id, activo) VALUES (?, ?, ?, ?, ?)",
        (nombre, numero, nacionalidad, escuderia_id, int(activo)),
    )
    conn.commit()
    return cur.lastrowid


def editar_piloto(conn: sqlite3.Connection, piloto_id: int, nombre: str, numero, nacionalidad: str, escuderia_id, activo: bool = True) -> None:
    nombre, nacionalidad = _texto(nombre, "Nombre"), _texto(nacionalidad, "Nacionalidad")
    numero, escuderia_id = _validar_piloto(conn, numero, escuderia_id, activo, piloto_id)
    conn.execute(
        "UPDATE pilotos SET nombre = ?, numero = ?, nacionalidad = ?, escuderia_id = ?, activo = ? WHERE id = ?",
        (nombre, numero, nacionalidad, escuderia_id, int(activo), piloto_id),
    )
    conn.commit()


def eliminar_piloto(conn: sqlite3.Connection, piloto_id: int) -> None:
    # RN-011: un piloto con resultados forma parte del campeonato.
    n = conn.execute("SELECT COUNT(*) FROM resultados WHERE piloto_id = ?", (piloto_id,)).fetchone()[0]
    if n:
        raise ReglaNegocioError("RN-011", f"El piloto tiene {n} resultado(s) registrados; no se puede eliminar.")
    conn.execute("DELETE FROM pilotos WHERE id = ?", (piloto_id,))
    conn.commit()


# ---------------------------------------------------------------- Carreras
def _fecha(valor: str) -> str:
    try:
        return date.fromisoformat(_texto(valor, "Fecha")).isoformat()
    except ValueError:
        raise DatoInvalido("La fecha debe tener el formato AAAA-MM-DD.") from None


def crear_carrera(conn: sqlite3.Connection, ronda, nombre: str, circuito: str, pais: str, fecha: str, sprint: bool = False) -> int:
    ronda = _entero(ronda, "Ronda")
    nombre, circuito, pais, fecha = _texto(nombre, "Nombre"), _texto(circuito, "Circuito"), _texto(pais, "País"), _fecha(fecha)
    if conn.execute("SELECT 1 FROM carreras WHERE ronda = ?", (ronda,)).fetchone():
        raise DatoInvalido(f"Ya existe la ronda {ronda}.")
    cur = conn.execute(
        "INSERT INTO carreras (ronda, nombre, circuito, pais, fecha, sprint) VALUES (?, ?, ?, ?, ?, ?)",
        (ronda, nombre, circuito, pais, fecha, int(bool(sprint))),
    )
    conn.commit()
    return cur.lastrowid


def editar_carrera(conn: sqlite3.Connection, carrera_id: int, ronda, nombre: str, circuito: str, pais: str, fecha: str, sprint: bool = False) -> None:
    ronda = _entero(ronda, "Ronda")
    nombre, circuito, pais, fecha = _texto(nombre, "Nombre"), _texto(circuito, "Circuito"), _texto(pais, "País"), _fecha(fecha)
    if conn.execute("SELECT 1 FROM carreras WHERE ronda = ? AND id <> ?", (ronda, carrera_id)).fetchone():
        raise DatoInvalido(f"Ya existe la ronda {ronda}.")
    if conn.execute("SELECT 1 FROM resultados WHERE carrera_id = ?", (carrera_id,)).fetchone():
        # RN-008: un evento con resultados ya se corrió.
        if date.fromisoformat(fecha) > date.today():
            raise ReglaNegocioError("RN-008", "El evento ya tiene resultados; su fecha no puede pasar al futuro.")
        if not sprint and conn.execute("SELECT 1 FROM resultados WHERE carrera_id = ? AND sesion = ?", (carrera_id, SPRINT)).fetchone():
            raise ReglaNegocioError("RN-008", "El evento tiene resultados de sprint; no puede dejar de ser fin de semana con sprint.")
    conn.execute(
        "UPDATE carreras SET ronda = ?, nombre = ?, circuito = ?, pais = ?, fecha = ?, sprint = ? WHERE id = ?",
        (ronda, nombre, circuito, pais, fecha, int(bool(sprint)), carrera_id),
    )
    conn.commit()


def eliminar_carrera(conn: sqlite3.Connection, carrera_id: int) -> None:
    conn.execute("DELETE FROM carreras WHERE id = ?", (carrera_id,))
    conn.commit()


# ---------------------------------------------------------------- Resultados
def registrar_resultados(
    conn: sqlite3.Connection, carrera_id: int, sesion: str, distancia: str, filas: list[tuple], hoy: date | None = None
) -> None:
    """Reemplaza los resultados de una sesión (carrera o sprint) de un evento.

    filas: lista de (piloto_id, posición o None, estado[, escuderia_id]). Con estado vacío y sin posición, el piloto
    no corrió. Si no se indica la escudería, se usa la que ya tenía registrada en esa sesión o la actual del piloto.
    """
    hoy = hoy or date.today()
    if sesion not in (CARRERA, SPRINT):
        raise DatoInvalido("La sesión debe ser carrera o sprint.")
    tabla_puntos(sesion, distancia)
    evento = conn.execute("SELECT fecha, sprint FROM carreras WHERE id = ?", (carrera_id,)).fetchone()
    if evento is None:
        raise DatoInvalido("El evento no existe.")
    # RN-008: solo eventos que ya se corrieron; sprint solo en fines de semana con sprint.
    if date.fromisoformat(evento["fecha"]) > hoy:
        raise ReglaNegocioError("RN-008", f"El evento es el {evento['fecha']}; todavía no se corre.")
    if sesion == SPRINT and not evento["sprint"]:
        raise ReglaNegocioError("RN-008", "Este fin de semana no tiene sprint.")

    previas = {
        r["piloto_id"]: r["escuderia_id"]
        for r in conn.execute("SELECT piloto_id, escuderia_id FROM resultados WHERE carrera_id = ? AND sesion = ?", (carrera_id, sesion))
    }
    vistos, posiciones, limpias, por_escuderia = set(), set(), [], Counter()
    for fila in filas:
        piloto_id, posicion, estado = fila[:3]
        escuderia_dada = fila[3] if len(fila) > 3 else None
        posicion = None if posicion in (None, "") else _entero(posicion, "Posición")
        estado = (estado or "").strip()
        if posicion is None and not estado:
            continue  # no corrió
        if posicion is not None and estado and estado != CLASIFICADO:
            raise ReglaNegocioError("RN-003", "Un piloto con abandono, descalificación o sin clasificar no lleva posición.")
        if posicion is None and estado not in ESTADOS_SIN_POSICION:
            raise DatoInvalido("El estado del resultado no es válido.")
        estado = CLASIFICADO if posicion is not None else estado
        # RN-007: un resultado por piloto y una posición por piloto.
        if piloto_id in vistos:
            raise ReglaNegocioError("RN-007", "Un piloto no puede tener dos resultados en la misma sesión.")
        if posicion is not None:
            if posicion < 1:
                raise DatoInvalido("La posición debe ser 1 o mayor.")
            if posicion in posiciones:
                raise ReglaNegocioError("RN-007", f"La posición {posicion} está asignada a más de un piloto.")
            posiciones.add(posicion)
        piloto = conn.execute("SELECT nombre, escuderia_id FROM pilotos WHERE id = ?", (piloto_id,)).fetchone()
        if piloto is None:
            raise DatoInvalido("Uno de los pilotos no existe.")
        escuderia_id = escuderia_dada or previas.get(piloto_id, piloto["escuderia_id"])
        por_escuderia[escuderia_id] += 1
        vistos.add(piloto_id)
        limpias.append((piloto_id, escuderia_id, posicion, estado))

    if posiciones and sorted(posiciones) != list(range(1, len(posiciones) + 1)):
        raise ReglaNegocioError("RN-007", "Las posiciones deben ser consecutivas desde el 1.er lugar, sin huecos.")
    # RN-004: dos autos por escudería en cada sesión.
    for escuderia_id, n in por_escuderia.items():
        if n > AUTOS_POR_ESCUDERIA:
            nombre = conn.execute("SELECT nombre FROM escuderias WHERE id = ?", (escuderia_id,)).fetchone()["nombre"]
            raise ReglaNegocioError("RN-004", f"{nombre} tiene {n} pilotos en la sesión; cada escudería corre con 2 autos.")
    # RN-005: máximo cuatro pilotos distintos por escudería en la temporada.
    for escuderia_id in por_escuderia:
        usados = {r[0] for r in conn.execute(
            "SELECT piloto_id FROM resultados WHERE escuderia_id = ? AND NOT (carrera_id = ? AND sesion = ?)", (escuderia_id, carrera_id, sesion)
        )}
        usados |= {p for p, e, _, _ in limpias if e == escuderia_id}
        if len(usados) > PILOTOS_POR_TEMPORADA:
            raise ReglaNegocioError("RN-005", f"Una escudería quedaría con {len(usados)} pilotos distintos en la temporada; el máximo es 4.")

    with conn:
        conn.execute("DELETE FROM resultados WHERE carrera_id = ? AND sesion = ?", (carrera_id, sesion))
        campo = "distancia" if sesion == CARRERA else "distancia_sprint"
        conn.execute(f"UPDATE carreras SET {campo} = ? WHERE id = ?", (distancia, carrera_id))
        conn.executemany(
            "INSERT INTO resultados (carrera_id, sesion, piloto_id, escuderia_id, posicion, estado, puntos) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(carrera_id, sesion, p, e, pos, est, puntos(sesion, distancia, pos, est)) for p, e, pos, est in limpias],
        )


# ---------------------------------------------------------------- Campeonatos (RN-009 y RN-010)
def _ordenar(filas: list[dict], posiciones: dict) -> list[dict]:
    """Ordena por puntos; en empate, más 1.os lugares en carreras, luego más 2.os, y así sucesivamente (A2.1.4c)."""
    maximo = max((p for conteo in posiciones.values() for p in conteo), default=0)

    def clave(f):
        conteo = posiciones.get(f["id"], Counter())
        return (-f["puntos"], *[-conteo[p] for p in range(1, maximo + 1)], f["nombre"])

    return sorted(filas, key=clave)


def _conteo_posiciones(conn, campo: str) -> dict:
    conteos: dict = {}
    for r in conn.execute(f"SELECT {campo} AS id, posicion FROM resultados WHERE sesion = ? AND posicion IS NOT NULL", (CARRERA,)):
        conteos.setdefault(r["id"], Counter())[r["posicion"]] += 1
    return conteos


def campeonato_pilotos(conn: sqlite3.Connection) -> list[dict]:
    filas = [
        dict(r)
        for r in conn.execute(
            """
            SELECT p.id, p.nombre, p.numero, p.nacionalidad, p.activo, e.nombre AS escuderia,
                   COALESCE(SUM(r.puntos), 0) AS puntos,
                   COALESCE(SUM(CASE WHEN r.sesion = 'carrera' AND r.posicion = 1 THEN 1 END), 0) AS victorias,
                   COALESCE(SUM(CASE WHEN r.sesion = 'carrera' AND r.posicion <= 3 THEN 1 END), 0) AS podios,
                   COALESCE(SUM(r.sesion = 'carrera'), 0) AS carreras
            FROM pilotos p
            JOIN escuderias e ON e.id = p.escuderia_id
            LEFT JOIN resultados r ON r.piloto_id = p.id
            GROUP BY p.id
            """
        )
    ]
    return _ordenar(filas, _conteo_posiciones(conn, "piloto_id"))


def campeonato_constructores(conn: sqlite3.Connection) -> list[dict]:
    filas = [
        dict(r)
        for r in conn.execute(
            """
            SELECT e.id, e.nombre, e.pais,
                   COALESCE(SUM(r.puntos), 0) AS puntos,
                   COALESCE(SUM(CASE WHEN r.sesion = 'carrera' AND r.posicion = 1 THEN 1 END), 0) AS victorias
            FROM escuderias e
            LEFT JOIN resultados r ON r.escuderia_id = e.id
            GROUP BY e.id
            """
        )
    ]
    return _ordenar(filas, _conteo_posiciones(conn, "escuderia_id"))
