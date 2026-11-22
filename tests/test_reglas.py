"""Una o más pruebas por regla de negocio; el nombre de cada prueba lleva la clave de su regla (test_rn###_...)."""
from datetime import date, timedelta

import pytest

from app import reglas
from app.reglas import ReglaNegocioError


@pytest.fixture
def parrilla(conn):
    """Dos escuderías, tres pilotos y una carrera ya corrida."""
    rb = reglas.crear_escuderia(conn, "Red Bull Racing", "Austria")
    fe = reglas.crear_escuderia(conn, "Ferrari", "Italia")
    ver = reglas.crear_piloto(conn, "Max Verstappen", 1, "Países Bajos", rb)
    per = reglas.crear_piloto(conn, "Sergio Pérez", 11, "México", rb)
    lec = reglas.crear_piloto(conn, "Charles Leclerc", 16, "Mónaco", fe)
    car = reglas.crear_carrera(conn, 1, "GP de Baréin", "Sakhir", "2024-03-02")
    return {"rb": rb, "fe": fe, "ver": ver, "per": per, "lec": lec, "car": car}


def _puntos(conn, piloto_id):
    return {r["id"]: r["puntos"] for r in reglas.campeonato_pilotos(conn)}[piloto_id]


def test_rn001_tabla_de_puntos_del_1_al_10():
    assert [reglas.puntos_por_posicion(p, False) for p in range(1, 11)] == [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def test_rn001_fuera_del_top_10_y_abandono_no_suman():
    assert reglas.puntos_por_posicion(11, False) == 0
    assert reglas.puntos_por_posicion(1, True) == 0


def test_rn001_los_puntos_se_guardan_al_registrar(conn, parrilla):
    reglas.registrar_resultados(conn, parrilla["car"], [(parrilla["ver"], 1, False), (parrilla["lec"], 2, False), (parrilla["per"], None, True)])
    assert _puntos(conn, parrilla["ver"]) == 25
    assert _puntos(conn, parrilla["lec"]) == 18
    assert _puntos(conn, parrilla["per"]) == 0


def test_rn002_maximo_dos_pilotos_por_escuderia(conn, parrilla):
    with pytest.raises(ReglaNegocioError) as e:
        reglas.crear_piloto(conn, "Liam Lawson", 30, "Nueva Zelanda", parrilla["rb"])
    assert e.value.regla == "RN-002"


def test_rn002_tampoco_al_cambiar_de_escuderia(conn, parrilla):
    with pytest.raises(ReglaNegocioError):
        reglas.editar_piloto(conn, parrilla["lec"], "Charles Leclerc", 16, "Mónaco", parrilla["rb"])
    # Editarse a sí mismo dentro de su escudería sí se permite
    reglas.editar_piloto(conn, parrilla["per"], "Checo Pérez", 11, "México", parrilla["rb"])


def test_rn003_numero_unico(conn, parrilla):
    with pytest.raises(ReglaNegocioError) as e:
        reglas.crear_piloto(conn, "Otro", 16, "México", parrilla["fe"])
    assert e.value.regla == "RN-003"


@pytest.mark.parametrize("numero", [0, 100, -5])
def test_rn003_numero_entre_1_y_99(conn, parrilla, numero):
    with pytest.raises(ReglaNegocioError):
        reglas.crear_piloto(conn, "Otro", numero, "México", parrilla["fe"])


def test_rn004_una_posicion_por_piloto(conn, parrilla):
    with pytest.raises(ReglaNegocioError) as e:
        reglas.registrar_resultados(conn, parrilla["car"], [(parrilla["ver"], 1, False), (parrilla["lec"], 1, False)])
    assert e.value.regla == "RN-004"


def test_rn004_posiciones_sin_huecos(conn, parrilla):
    with pytest.raises(ReglaNegocioError):
        reglas.registrar_resultados(conn, parrilla["car"], [(parrilla["ver"], 1, False), (parrilla["lec"], 3, False)])


def test_rn004_un_resultado_por_piloto(conn, parrilla):
    with pytest.raises(ReglaNegocioError):
        reglas.registrar_resultados(conn, parrilla["car"], [(parrilla["ver"], 1, False), (parrilla["ver"], 2, False)])


def test_rn005_no_hay_resultados_de_una_carrera_futura(conn, parrilla):
    manana = (date.today() + timedelta(days=1)).isoformat()
    futura = reglas.crear_carrera(conn, 2, "GP del futuro", "Circuito X", manana)
    with pytest.raises(ReglaNegocioError) as e:
        reglas.registrar_resultados(conn, futura, [(parrilla["ver"], 1, False)])
    assert e.value.regla == "RN-005"
    assert conn.execute("SELECT COUNT(*) FROM resultados WHERE carrera_id = ?", (futura,)).fetchone()[0] == 0


def test_rn006_no_se_elimina_piloto_con_resultados(conn, parrilla):
    reglas.registrar_resultados(conn, parrilla["car"], [(parrilla["ver"], 1, False)])
    with pytest.raises(ReglaNegocioError) as e:
        reglas.eliminar_piloto(conn, parrilla["ver"])
    assert e.value.regla == "RN-006"
    reglas.eliminar_piloto(conn, parrilla["per"])  # sin resultados: sí se elimina


def test_rn006_no_se_elimina_escuderia_con_pilotos(conn, parrilla):
    with pytest.raises(ReglaNegocioError):
        reglas.eliminar_escuderia(conn, parrilla["fe"])


def test_rn007_ordena_por_puntos(conn, parrilla):
    reglas.registrar_resultados(conn, parrilla["car"], [(parrilla["lec"], 1, False), (parrilla["ver"], 2, False), (parrilla["per"], 3, False)])
    assert [r["nombre"] for r in reglas.campeonato_pilotos(conn)] == ["Charles Leclerc", "Max Verstappen", "Sergio Pérez"]


def test_rn007_en_empate_gana_quien_tiene_mas_victorias(conn, parrilla):
    me = reglas.crear_escuderia(conn, "Mercedes", "Alemania")
    mc = reglas.crear_escuderia(conn, "McLaren", "Reino Unido")
    ham = reglas.crear_piloto(conn, "Lewis Hamilton", 44, "Reino Unido", me)
    rus = reglas.crear_piloto(conn, "George Russell", 63, "Reino Unido", me)
    nor = reglas.crear_piloto(conn, "Lando Norris", 4, "Reino Unido", mc)
    c2 = reglas.crear_carrera(conn, 2, "GP de Arabia Saudita", "Yeda", "2024-03-09")
    p = parrilla
    # Pérez gana la 1 (25). Leclerc: 3.º (15) + 5.º (10) = 25, sin victorias.
    reglas.registrar_resultados(conn, p["car"], [(p["per"], 1, False), (p["ver"], 2, False), (p["lec"], 3, False), (ham, 4, False), (rus, 5, False)])
    reglas.registrar_resultados(conn, c2, [(p["ver"], 1, False), (ham, 2, False), (rus, 3, False), (nor, 4, False), (p["lec"], 5, False)])
    tabla = reglas.campeonato_pilotos(conn)
    pts = {r["id"]: r["puntos"] for r in tabla}
    assert pts[p["per"]] == pts[p["lec"]] == 25
    orden = [r["id"] for r in tabla]
    # Por orden alfabético Leclerc iría primero; la victoria pone a Pérez adelante.
    assert orden.index(p["per"]) < orden.index(p["lec"])
