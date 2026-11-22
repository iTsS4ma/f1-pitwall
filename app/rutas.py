"""Pantallas de la aplicación."""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import reglas
from .db import get_db
from .reglas import DatoInvalido, ReglaNegocioError

bp = Blueprint("pitwall", __name__)


def _intentar(accion, exito: str) -> bool:
    """Ejecuta una operación y muestra el resultado; devuelve True si salió bien."""
    try:
        accion()
    except (ReglaNegocioError, DatoInvalido) as e:
        flash(str(e), "error")
        return False
    flash(exito, "ok")
    return True


def _uno(sql: str, *args):
    fila = get_db().execute(sql, args).fetchone()
    if fila is None:
        abort(404)
    return fila


def _hoy() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------- Inicio
@bp.get("/")
def inicio():
    conn = get_db()
    carreras = conn.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM resultados r WHERE r.carrera_id = c.id AND r.sesion = 'carrera') AS n,
                  (SELECT p.nombre FROM resultados r JOIN pilotos p ON p.id = r.piloto_id
                   WHERE r.carrera_id = c.id AND r.sesion = 'carrera' AND r.posicion = 1) AS ganador
           FROM carreras c ORDER BY ronda"""
    ).fetchall()
    corridas = [c for c in carreras if c["n"]]
    return render_template(
        "inicio.html",
        pilotos=reglas.campeonato_pilotos(conn),
        constructores=reglas.campeonato_constructores(conn),
        ultima=corridas[-1] if corridas else None,
        proximas=[c for c in carreras if not c["n"]][:3],
        total=len(carreras),
    )


# ---------------------------------------------------------------- Escuderías
def _lista_escuderias():
    return get_db().execute(
        """SELECT e.*,
                  (SELECT COUNT(*) FROM pilotos p WHERE p.escuderia_id = e.id AND p.activo = 1) AS activos,
                  (SELECT COUNT(*) FROM (SELECT piloto_id FROM resultados r WHERE r.escuderia_id = e.id
                                         UNION SELECT id FROM pilotos p WHERE p.escuderia_id = e.id)) AS usados,
                  (SELECT group_concat(nombre, ', ') FROM (SELECT nombre FROM pilotos p WHERE p.escuderia_id = e.id AND p.activo = 1 ORDER BY numero)) AS titulares
           FROM escuderias e ORDER BY nombre"""
    ).fetchall()


@bp.route("/escuderias", methods=["GET", "POST"])
def escuderias():
    if request.method == "POST":
        f = request.form
        if _intentar(lambda: reglas.crear_escuderia(get_db(), f["nombre"], f["pais"]), "Escudería registrada."):
            return redirect(url_for(".escuderias"))
    return render_template("escuderias.html", escuderias=_lista_escuderias(), form=request.form)


@bp.route("/escuderias/<int:eid>/editar", methods=["GET", "POST"])
def editar_escuderia(eid):
    esc = _uno("SELECT * FROM escuderias WHERE id = ?", eid)
    if request.method == "POST":
        f = request.form
        if _intentar(lambda: reglas.editar_escuderia(get_db(), eid, f["nombre"], f["pais"]), "Escudería actualizada."):
            return redirect(url_for(".escuderias"))
    return render_template("escuderia_editar.html", esc=esc, form=request.form or esc)


@bp.post("/escuderias/<int:eid>/eliminar")
def eliminar_escuderia(eid):
    _intentar(lambda: reglas.eliminar_escuderia(get_db(), eid), "Escudería eliminada.")
    return redirect(url_for(".escuderias"))


# ---------------------------------------------------------------- Pilotos
@bp.route("/pilotos", methods=["GET", "POST"])
def pilotos():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        accion = lambda: reglas.crear_piloto(conn, f["nombre"], f["numero"], f["nacionalidad"], f.get("escuderia_id"), f.get("activo") == "1")
        if _intentar(accion, "Piloto registrado."):
            return redirect(url_for(".pilotos"))
    filas = conn.execute(
        """SELECT p.*, e.nombre AS escuderia,
                  (SELECT COUNT(*) FROM resultados r WHERE r.piloto_id = p.id AND r.sesion = 'carrera') AS n,
                  (SELECT COALESCE(SUM(puntos), 0) FROM resultados r WHERE r.piloto_id = p.id) AS puntos
           FROM pilotos p JOIN escuderias e ON e.id = p.escuderia_id ORDER BY p.activo DESC, e.nombre, p.numero"""
    ).fetchall()
    return render_template("pilotos.html", pilotos=filas, escuderias=_lista_escuderias(), form=request.form or {"activo": 1})


@bp.route("/pilotos/<int:pid>/editar", methods=["GET", "POST"])
def editar_piloto(pid):
    pil = _uno("SELECT * FROM pilotos WHERE id = ?", pid)
    if request.method == "POST":
        f = request.form
        accion = lambda: reglas.editar_piloto(get_db(), pid, f["nombre"], f["numero"], f["nacionalidad"], f.get("escuderia_id"), f.get("activo") == "1")
        if _intentar(accion, "Piloto actualizado."):
            return redirect(url_for(".pilotos"))
    return render_template("piloto_editar.html", pil=pil, escuderias=_lista_escuderias(), form=request.form or pil)


@bp.post("/pilotos/<int:pid>/eliminar")
def eliminar_piloto(pid):
    _intentar(lambda: reglas.eliminar_piloto(get_db(), pid), "Piloto eliminado.")
    return redirect(url_for(".pilotos"))


# ---------------------------------------------------------------- Carreras
def _datos_carrera(f):
    return f.get("ronda"), f.get("nombre"), f.get("circuito"), f.get("pais"), f.get("fecha"), f.get("sprint") == "1"


@bp.route("/carreras", methods=["GET", "POST"])
def carreras():
    conn = get_db()
    if request.method == "POST":
        if _intentar(lambda: reglas.crear_carrera(conn, *_datos_carrera(request.form)), "Evento registrado."):
            return redirect(url_for(".carreras"))
    filas = conn.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM resultados r WHERE r.carrera_id = c.id AND r.sesion = 'carrera') AS n,
                  (SELECT p.nombre FROM resultados r JOIN pilotos p ON p.id = r.piloto_id
                   WHERE r.carrera_id = c.id AND r.sesion = 'carrera' AND r.posicion = 1) AS ganador
           FROM carreras c ORDER BY ronda"""
    ).fetchall()
    sig = (conn.execute("SELECT MAX(ronda) FROM carreras").fetchone()[0] or 0) + 1
    return render_template("carreras.html", carreras=filas, form=request.form, siguiente=sig, hoy=_hoy())


@bp.route("/carreras/<int:cid>/editar", methods=["GET", "POST"])
def editar_carrera(cid):
    car = _uno("SELECT * FROM carreras WHERE id = ?", cid)
    if request.method == "POST":
        if _intentar(lambda: reglas.editar_carrera(get_db(), cid, *_datos_carrera(request.form)), "Evento actualizado."):
            return redirect(url_for(".carrera", cid=cid))
    return render_template("carrera_editar.html", car=car, form=request.form or car)


@bp.post("/carreras/<int:cid>/eliminar")
def eliminar_carrera(cid):
    _intentar(lambda: reglas.eliminar_carrera(get_db(), cid), "Evento eliminado junto con sus resultados.")
    return redirect(url_for(".carreras"))


@bp.route("/carreras/<int:cid>", methods=["GET", "POST"])
def carrera(cid):
    conn = get_db()
    car = _uno("SELECT * FROM carreras WHERE id = ?", cid)
    sesion = request.values.get("sesion", reglas.CARRERA)
    if sesion not in (reglas.CARRERA, reglas.SPRINT) or (sesion == reglas.SPRINT and not car["sprint"]):
        abort(404)
    distancias = reglas.DISTANCIAS_CARRERA if sesion == reglas.CARRERA else reglas.DISTANCIAS_SPRINT
    registrados = {
        r["piloto_id"]: r
        for r in conn.execute("SELECT * FROM resultados WHERE carrera_id = ? AND sesion = ?", (cid, sesion))
    }
    # En el formulario aparecen los pilotos activos y los que ya tienen resultado en esta sesión.
    pilotos = [
        p
        for p in conn.execute(
            """SELECT p.*, e.nombre AS escuderia FROM pilotos p JOIN escuderias e ON e.id = p.escuderia_id
               ORDER BY e.nombre, p.numero"""
        ).fetchall()
        if p["activo"] or p["id"] in registrados
    ]
    if request.method == "POST":
        f = request.form
        filas = [(p["id"], f.get(f"pos_{p['id']}"), f.get(f"estado_{p['id']}")) for p in pilotos]
        accion = lambda: reglas.registrar_resultados(conn, cid, sesion, f.get("distancia"), filas)
        if _intentar(accion, "Resultados guardados."):
            return redirect(url_for(".carrera", cid=cid, sesion=sesion))
        actuales = {p["id"]: (f.get(f"pos_{p['id']}") or "", f.get(f"estado_{p['id']}") or "") for p in pilotos}
        distancia = f.get("distancia")
    else:
        actuales = {
            pid: ("" if r["posicion"] is None else str(r["posicion"]), "" if r["estado"] == reglas.CLASIFICADO else r["estado"])
            for pid, r in registrados.items()
        }
        distancia = car["distancia"] if sesion == reglas.CARRERA else car["distancia_sprint"]
    resultados = conn.execute(
        """SELECT r.*, p.nombre, p.numero, e.nombre AS escuderia FROM resultados r
           JOIN pilotos p ON p.id = r.piloto_id JOIN escuderias e ON e.id = r.escuderia_id
           WHERE r.carrera_id = ? AND r.sesion = ?
           ORDER BY r.posicion IS NULL, r.posicion, p.nombre""",
        (cid, sesion),
    ).fetchall()
    return render_template(
        "carrera.html",
        car=car,
        sesion=sesion,
        pilotos=pilotos,
        resultados=resultados,
        actuales=actuales,
        distancias=distancias,
        distancia=distancia,
        estados=reglas.ESTADOS_SIN_POSICION,
        futura=car["fecha"] > _hoy(),
    )


@bp.app_errorhandler(404)
def no_encontrado(_e):
    return render_template("404.html"), 404
