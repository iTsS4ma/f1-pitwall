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
    except ReglaNegocioError as e:
        flash(f"{e.regla} · {e.mensaje}", "regla")
        return False
    except DatoInvalido as e:
        flash(str(e), "error")
        return False
    flash(exito, "ok")
    return True


def _uno(sql: str, *args):
    fila = get_db().execute(sql, args).fetchone()
    if fila is None:
        abort(404)
    return fila


# ---------------------------------------------------------------- Inicio
@bp.get("/")
def inicio():
    conn = get_db()
    return render_template(
        "inicio.html",
        pilotos=reglas.campeonato_pilotos(conn),
        constructores=reglas.campeonato_constructores(conn),
        carreras=conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM resultados r WHERE r.carrera_id = c.id) AS n FROM carreras c ORDER BY ronda"
        ).fetchall(),
    )


# ---------------------------------------------------------------- Escuderías
@bp.route("/escuderias", methods=["GET", "POST"])
def escuderias():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        if _intentar(lambda: reglas.crear_escuderia(conn, f["nombre"], f["pais"]), "Escudería registrada."):
            return redirect(url_for(".escuderias"))
    filas = conn.execute(
        "SELECT e.*, (SELECT COUNT(*) FROM pilotos p WHERE p.escuderia_id = e.id) AS n FROM escuderias e ORDER BY nombre"
    ).fetchall()
    return render_template("escuderias.html", escuderias=filas, form=request.form)


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
def _lista_escuderias():
    return get_db().execute(
        "SELECT e.*, (SELECT COUNT(*) FROM pilotos p WHERE p.escuderia_id = e.id) AS n FROM escuderias e ORDER BY nombre"
    ).fetchall()


@bp.route("/pilotos", methods=["GET", "POST"])
def pilotos():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        accion = lambda: reglas.crear_piloto(conn, f["nombre"], f["numero"], f["nacionalidad"], f.get("escuderia_id"))
        if _intentar(accion, "Piloto registrado."):
            return redirect(url_for(".pilotos"))
    filas = conn.execute(
        """SELECT p.*, e.nombre AS escuderia,
                  (SELECT COUNT(*) FROM resultados r WHERE r.piloto_id = p.id) AS n
           FROM pilotos p JOIN escuderias e ON e.id = p.escuderia_id ORDER BY e.nombre, p.numero"""
    ).fetchall()
    return render_template("pilotos.html", pilotos=filas, escuderias=_lista_escuderias(), form=request.form)


@bp.route("/pilotos/<int:pid>/editar", methods=["GET", "POST"])
def editar_piloto(pid):
    pil = _uno("SELECT * FROM pilotos WHERE id = ?", pid)
    if request.method == "POST":
        f = request.form
        accion = lambda: reglas.editar_piloto(get_db(), pid, f["nombre"], f["numero"], f["nacionalidad"], f.get("escuderia_id"))
        if _intentar(accion, "Piloto actualizado."):
            return redirect(url_for(".pilotos"))
    return render_template("piloto_editar.html", pil=pil, escuderias=_lista_escuderias(), form=request.form or pil)


@bp.post("/pilotos/<int:pid>/eliminar")
def eliminar_piloto(pid):
    _intentar(lambda: reglas.eliminar_piloto(get_db(), pid), "Piloto eliminado.")
    return redirect(url_for(".pilotos"))


# ---------------------------------------------------------------- Carreras
@bp.route("/carreras", methods=["GET", "POST"])
def carreras():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        accion = lambda: reglas.crear_carrera(conn, f["ronda"], f["nombre"], f["circuito"], f["fecha"])
        if _intentar(accion, "Carrera registrada."):
            return redirect(url_for(".carreras"))
    filas = conn.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM resultados r WHERE r.carrera_id = c.id) AS n,
                  (SELECT p.nombre FROM resultados r JOIN pilotos p ON p.id = r.piloto_id
                   WHERE r.carrera_id = c.id AND r.posicion = 1) AS ganador
           FROM carreras c ORDER BY ronda"""
    ).fetchall()
    sig = (conn.execute("SELECT MAX(ronda) FROM carreras").fetchone()[0] or 0) + 1
    return render_template("carreras.html", carreras=filas, form=request.form, siguiente=sig, hoy=date.today().isoformat())


@bp.route("/carreras/<int:cid>/editar", methods=["GET", "POST"])
def editar_carrera(cid):
    car = _uno("SELECT * FROM carreras WHERE id = ?", cid)
    if request.method == "POST":
        f = request.form
        accion = lambda: reglas.editar_carrera(get_db(), cid, f["ronda"], f["nombre"], f["circuito"], f["fecha"])
        if _intentar(accion, "Carrera actualizada."):
            return redirect(url_for(".carrera", cid=cid))
    return render_template("carrera_editar.html", car=car, form=request.form or car)


@bp.post("/carreras/<int:cid>/eliminar")
def eliminar_carrera(cid):
    _intentar(lambda: reglas.eliminar_carrera(get_db(), cid), "Carrera eliminada junto con sus resultados.")
    return redirect(url_for(".carreras"))


@bp.route("/carreras/<int:cid>", methods=["GET", "POST"])
def carrera(cid):
    conn = get_db()
    car = _uno("SELECT * FROM carreras WHERE id = ?", cid)
    pilotos = conn.execute(
        "SELECT p.*, e.nombre AS escuderia FROM pilotos p JOIN escuderias e ON e.id = p.escuderia_id ORDER BY e.nombre, p.numero"
    ).fetchall()
    if request.method == "POST":
        f = request.form
        filas = [(p["id"], f.get(f"pos_{p['id']}"), f.get(f"dnf_{p['id']}") == "1") for p in pilotos]
        if _intentar(lambda: reglas.registrar_resultados(conn, cid, filas), "Resultados guardados."):
            return redirect(url_for(".carrera", cid=cid))
        actuales = {p["id"]: (f.get(f"pos_{p['id']}") or "", f.get(f"dnf_{p['id']}") == "1") for p in pilotos}
    else:
        actuales = {
            r["piloto_id"]: (str(r["posicion"] or ""), bool(r["abandono"]))
            for r in conn.execute("SELECT * FROM resultados WHERE carrera_id = ?", (cid,))
        }
    resultados = conn.execute(
        """SELECT r.*, p.nombre, p.numero, e.nombre AS escuderia FROM resultados r
           JOIN pilotos p ON p.id = r.piloto_id JOIN escuderias e ON e.id = p.escuderia_id
           WHERE r.carrera_id = ? ORDER BY r.abandono, r.posicion""",
        (cid,),
    ).fetchall()
    futura = car["fecha"] > date.today().isoformat()
    return render_template(
        "carrera.html", car=car, pilotos=pilotos, resultados=resultados, actuales=actuales, futura=futura, n=len(pilotos)
    )


@bp.app_errorhandler(404)
def no_encontrado(_e):
    return render_template("404.html"), 404
