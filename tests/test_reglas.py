"""Pruebas de las reglas de negocio; el nombre de cada prueba lleva la clave de su regla (test_rn###_...)."""
from datetime import date, timedelta

import pytest

from app import reglas
from app.reglas import CARRERA, SPRINT, ReglaNegocioError


@pytest.fixture
def t(conn):
    """Tres escuderías, cinco pilotos y un fin de semana con sprint ya corrido."""
    me = reglas.crear_escuderia(conn, "Mercedes", "Alemania")
    rb = reglas.crear_escuderia(conn, "Red Bull Racing", "Austria")
    fe = reglas.crear_escuderia(conn, "Ferrari", "Italia")
    d = {
        "me": me, "rb": rb, "fe": fe,
        "ant": reglas.crear_piloto(conn, "Andrea Kimi Antonelli", 12, "Italia", me),
        "rus": reglas.crear_piloto(conn, "George Russell", 63, "Reino Unido", me),
        "ver": reglas.crear_piloto(conn, "Max Verstappen", 3, "Países Bajos", rb),
        "had": reglas.crear_piloto(conn, "Isack Hadjar", 6, "Francia", rb),
        "lec": reglas.crear_piloto(conn, "Charles Leclerc", 16, "Mónaco", fe),
    }
    d["c1"] = reglas.crear_carrera(conn, 1, "GP de China", "Shanghái", "China", "2026-03-15", sprint=True)
    d["c2"] = reglas.crear_carrera(conn, 2, "GP de Japón", "Suzuka", "Japón", "2026-03-29")
    return d


def _pts(conn, pid):
    return {r["id"]: r["puntos"] for r in reglas.campeonato_pilotos(conn)}[pid]


def _carrera(conn, cid, orden, distancia=None, sesion=CARRERA):
    distancia = distancia or ("75" if sesion == CARRERA else "50")
    reglas.registrar_resultados(conn, cid, sesion, distancia, [(p, i, "") for i, p in enumerate(orden, start=1)])


# RN-001 · Puntos de carrera según la distancia completada (FIA A2.2.1)
def test_rn001_distancia_completa_25_a_1():
    assert [reglas.puntos(CARRERA, "75", p) for p in range(1, 12)] == [25, 18, 15, 12, 10, 8, 6, 4, 2, 1, 0]


@pytest.mark.parametrize("distancia,primero,ultimo_con_puntos", [("2v", 6, 5), ("25", 13, 9), ("50", 19, 10)])
def test_rn001_carrera_acortada(distancia, primero, ultimo_con_puntos):
    assert reglas.puntos(CARRERA, distancia, 1) == primero
    assert reglas.puntos(CARRERA, distancia, ultimo_con_puntos) == 1
    assert reglas.puntos(CARRERA, distancia, ultimo_con_puntos + 1) == 0


def test_rn001_menos_de_dos_vueltas_no_da_puntos(conn, t):
    _carrera(conn, t["c2"], [t["ver"], t["lec"]], distancia="menos2")
    assert _pts(conn, t["ver"]) == 0


# RN-002 · Puntos de sprint (FIA A2.2.2)
def test_rn002_sprint_8_a_1(conn, t):
    assert [reglas.puntos(SPRINT, "50", p) for p in range(1, 10)] == [8, 7, 6, 5, 4, 3, 2, 1, 0]
    _carrera(conn, t["c1"], [t["ant"], t["rus"]], sesion=SPRINT)
    _carrera(conn, t["c1"], [t["rus"], t["ant"]])
    assert _pts(conn, t["ant"]) == 8 + 18
    assert _pts(conn, t["rus"]) == 7 + 25


def test_rn002_sprint_corto_no_da_puntos():
    assert reglas.puntos(SPRINT, "menos50", 1) == 0


# RN-003 · Solo suman los clasificados
def test_rn003_abandono_no_suma_ni_lleva_posicion(conn, t):
    reglas.registrar_resultados(conn, t["c2"], CARRERA, "75", [(t["ver"], 1, ""), (t["lec"], None, "Abandono"), (t["ant"], None, "Descalificado")])
    assert _pts(conn, t["lec"]) == 0 and _pts(conn, t["ant"]) == 0
    with pytest.raises(ReglaNegocioError) as e:
        reglas.registrar_resultados(conn, t["c2"], CARRERA, "75", [(t["ver"], 1, "Abandono")])
    assert e.value.regla == "RN-003"


# RN-004 · Dos autos por escudería (FIA A2.1.3)
def test_rn004_maximo_dos_activos(conn, t):
    with pytest.raises(ReglaNegocioError) as e:
        reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", t["rb"])
    assert e.value.regla == "RN-004"
    reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", t["rb"], activo=False)  # como reserva sí


def test_rn004_maximo_dos_por_sesion(conn, t):
    law = reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", t["rb"], activo=False)
    with pytest.raises(ReglaNegocioError) as e:
        _carrera(conn, t["c2"], [t["ver"], t["had"], law])
    assert e.value.regla == "RN-004"


# RN-005 · Máximo 4 pilotos por escudería en la temporada (FIA B1.7.1)
def test_rn005_cuatro_pilotos_por_temporada(conn, t):
    reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", t["rb"], activo=False)
    reglas.crear_piloto(conn, "Yuki Tsunoda", 22, "Japón", t["rb"], activo=False)
    with pytest.raises(ReglaNegocioError) as e:
        reglas.crear_piloto(conn, "Quinto Piloto", 99, "México", t["rb"], activo=False)
    assert e.value.regla == "RN-005"


def test_rn005_cuenta_a_quien_ya_corrio_aunque_se_haya_ido(conn, t):
    reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", t["rb"], activo=False)
    reglas.crear_piloto(conn, "Yuki Tsunoda", 22, "Japón", t["rb"], activo=False)
    _carrera(conn, t["c2"], [t["ver"], t["had"]])
    reglas.editar_piloto(conn, t["had"], "Isack Hadjar", 6, "Francia", t["fe"], activo=False)  # Hadjar se va
    with pytest.raises(ReglaNegocioError):
        reglas.crear_piloto(conn, "Otro", 99, "México", t["rb"], activo=False)


# RN-006 · Número de piloto
def test_rn006_numero_unico(conn, t):
    with pytest.raises(ReglaNegocioError) as e:
        reglas.crear_piloto(conn, "Otro", 16, "México", t["fe"])
    assert e.value.regla == "RN-006"


@pytest.mark.parametrize("numero", [0, 100])
def test_rn006_numero_entre_1_y_99(conn, t, numero):
    with pytest.raises(ReglaNegocioError):
        reglas.crear_piloto(conn, "Otro", numero, "México", t["fe"])


# RN-007 · Clasificación consistente
def test_rn007_posicion_repetida(conn, t):
    with pytest.raises(ReglaNegocioError) as e:
        reglas.registrar_resultados(conn, t["c2"], CARRERA, "75", [(t["ver"], 1, ""), (t["lec"], 1, "")])
    assert e.value.regla == "RN-007"


def test_rn007_posiciones_sin_huecos(conn, t):
    with pytest.raises(ReglaNegocioError):
        reglas.registrar_resultados(conn, t["c2"], CARRERA, "75", [(t["ver"], 1, ""), (t["lec"], 3, "")])


def test_rn007_un_resultado_por_piloto(conn, t):
    with pytest.raises(ReglaNegocioError):
        reglas.registrar_resultados(conn, t["c2"], CARRERA, "75", [(t["ver"], 1, ""), (t["ver"], 2, "")])


# RN-008 · Solo eventos ya corridos; sprint solo en fin de semana con sprint
def test_rn008_evento_futuro(conn, t):
    manana = (date.today() + timedelta(days=1)).isoformat()
    futura = reglas.crear_carrera(conn, 3, "GP del futuro", "X", "México", manana)
    with pytest.raises(ReglaNegocioError) as e:
        _carrera(conn, futura, [t["ver"]])
    assert e.value.regla == "RN-008"


def test_rn008_sprint_en_fin_de_semana_normal(conn, t):
    with pytest.raises(ReglaNegocioError) as e:
        _carrera(conn, t["c2"], [t["ver"]], sesion=SPRINT)
    assert e.value.regla == "RN-008"


# RN-009 · Campeonato de pilotos y desempate (FIA A2.1.4c)
def test_rn009_empate_lo_gana_quien_tiene_mas_victorias(conn, t):
    _carrera(conn, t["c1"], [t["ant"], t["lec"]], sesion=SPRINT)  # Leclerc 7 de sprint
    _carrera(conn, t["c1"], [t["ver"], t["lec"]])  # Verstappen 25 · Leclerc 18 + 7 = 25
    assert _pts(conn, t["ver"]) == _pts(conn, t["lec"]) == 25
    orden = [r["id"] for r in reglas.campeonato_pilotos(conn)]
    assert orden.index(t["ver"]) < orden.index(t["lec"])


def test_rn009_los_sprints_no_cuentan_para_desempatar(conn, t):
    ham = reglas.crear_piloto(conn, "Lewis Hamilton", 44, "Reino Unido", t["fe"])
    # Sprint: Russell gana (8) y Antonelli es 6.º (3).
    _carrera(conn, t["c1"], [t["rus"], t["ver"], t["had"], t["lec"], ham, t["ant"]], sesion=SPRINT)
    # Carrera: Antonelli 3.º (15) y Russell 5.º (10). Los dos suman 18.
    _carrera(conn, t["c1"], [t["ver"], t["had"], t["ant"], t["lec"], t["rus"]])
    assert _pts(conn, t["rus"]) == _pts(conn, t["ant"]) == 18
    # Ninguno ganó ni fue 2.º en una carrera; Antonelli tiene un 3.er lugar en carrera. La victoria de sprint no cuenta.
    orden = [r["id"] for r in reglas.campeonato_pilotos(conn)]
    assert orden.index(t["ant"]) < orden.index(t["rus"])


def test_rn009_con_mismas_victorias_deciden_los_segundos_lugares(conn, t):
    c3 = reglas.crear_carrera(conn, 3, "GP 3", "X", "X", "2026-04-05")
    c4 = reglas.crear_carrera(conn, 4, "GP 4", "X", "X", "2026-04-12")
    _carrera(conn, t["c2"], [t["ver"], t["ant"], t["lec"]])           # ver 25 · ant 18
    _carrera(conn, c3, [t["ant"], t["lec"], t["ver"]])                 # ant 25 · ver 15
    _carrera(conn, c4, [t["lec"], t["had"], t["ver"], t["ant"]])       # ver 15 · ant 12
    assert _pts(conn, t["ver"]) == _pts(conn, t["ant"]) == 55          # 1 victoria cada uno
    orden = [r["id"] for r in reglas.campeonato_pilotos(conn)]
    assert orden.index(t["ant"]) < orden.index(t["ver"])               # Antonelli tiene un 2.º lugar


# RN-010 · Constructores: suma de los dos autos con la escudería con la que corrieron
def test_rn010_puntos_van_a_la_escuderia_de_ese_evento(conn, t):
    law = reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", t["fe"], activo=False)
    reglas.registrar_resultados(conn, t["c2"], CARRERA, "75", [(law, 1, "", t["rb"]), (t["ver"], 2, "")])
    tabla = {r["id"]: r["puntos"] for r in reglas.campeonato_constructores(conn)}
    assert tabla[t["rb"]] == 25 + 18
    assert tabla[t["fe"]] == 0


# RN-011 · No se borra lo que tiene historial
def test_rn011_piloto_con_resultados(conn, t):
    _carrera(conn, t["c2"], [t["ver"]])
    with pytest.raises(ReglaNegocioError) as e:
        reglas.eliminar_piloto(conn, t["ver"])
    assert e.value.regla == "RN-011"
    reglas.eliminar_piloto(conn, t["lec"])


def test_rn011_escuderia_con_pilotos(conn, t):
    with pytest.raises(ReglaNegocioError):
        reglas.eliminar_escuderia(conn, t["fe"])
