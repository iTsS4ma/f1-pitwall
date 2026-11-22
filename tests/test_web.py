"""Pruebas de las pantallas con la temporada 2026 cargada."""
import pytest


@pytest.mark.parametrize("ruta", ["/", "/carreras", "/pilotos", "/escuderias", "/carreras/1", "/carreras/2?sesion=sprint", "/carreras/1/editar", "/pilotos/1/editar"])
def test_pantallas_cargan(cliente, ruta):
    assert cliente.get(ruta).status_code == 200


def test_sprint_en_fin_de_semana_sin_sprint_da_404(cliente):
    assert cliente.get("/carreras/1?sesion=sprint").status_code == 404


def test_inicio_muestra_el_lider_del_campeonato(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert "Andrea Kimi Antonelli" in html and "<strong>390</strong>" in html


def test_pantallas_no_muestran_claves_de_reglas(cliente):
    for ruta in ["/", "/carreras", "/pilotos", "/escuderias", "/carreras/2", "/carreras/2?sesion=sprint"]:
        assert "RN-0" not in cliente.get(ruta).get_data(as_text=True)


def test_ruta_inexistente_da_404(cliente):
    assert cliente.get("/pilotos/999/editar").status_code == 404


def test_web_rn004_avisa_escuderia_con_dos_activos(cliente):
    r = cliente.post("/pilotos", data={"nombre": "Nuevo", "numero": "99", "nacionalidad": "México", "escuderia_id": "1", "activo": "1"}, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "pilotos activos" in html and "RN-0" not in html


def test_web_rn011_avisa_piloto_con_resultados(cliente):
    r = cliente.post("/pilotos/1/eliminar", follow_redirects=True)
    assert "no se puede eliminar" in r.get_data(as_text=True)


def test_web_crud_de_escuderia(cliente):
    cliente.post("/escuderias", data={"nombre": "Escudería de prueba", "pais": "México"})
    html = cliente.get("/escuderias").get_data(as_text=True)
    assert "Escudería de prueba" in html
    r = cliente.post("/escuderias/12/eliminar", follow_redirects=True)
    assert "Escudería eliminada" in r.get_data(as_text=True)


def test_web_corregir_resultados_conserva_los_puntos(cliente):
    """Volver a guardar desde la pantalla el resultado real del GP de Australia no cambia el campeonato."""
    from app.db import conectar

    conn = conectar(cliente.application.config["DATABASE"])
    datos = {"sesion": "carrera", "distancia": "75"}
    for r in conn.execute("SELECT piloto_id, posicion, estado FROM resultados WHERE carrera_id = 1 AND sesion = 'carrera'"):
        if r["posicion"]:
            datos[f"pos_{r['piloto_id']}"] = str(r["posicion"])
        else:
            datos[f"estado_{r['piloto_id']}"] = r["estado"]
    conn.close()
    r = cliente.post("/carreras/1", data=datos, follow_redirects=True)
    assert "Resultados guardados" in r.get_data(as_text=True)
    assert "<strong>390</strong>" in cliente.get("/").get_data(as_text=True)


def test_web_avisa_posicion_repetida_sin_guardar(cliente):
    r = cliente.post("/carreras/1", data={"sesion": "carrera", "distancia": "75", "pos_1": "1", "pos_2": "1"}, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "más de un piloto" in html and "RN-0" not in html
    assert "<strong>390</strong>" in cliente.get("/").get_data(as_text=True)
