"""Pruebas de las pantallas: que carguen y que muestren el aviso de la regla incumplida."""
import pytest


@pytest.mark.parametrize("ruta", ["/", "/carreras", "/pilotos", "/escuderias", "/carreras/1"])
def test_pantallas_cargan(cliente, ruta):
    r = cliente.get(ruta)
    assert r.status_code == 200


def test_inicio_muestra_campeonato_con_datos_de_ejemplo(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert "Max Verstappen" in html
    assert "<strong>25</strong>" in html  # ganador del GP de Baréin 2024


def test_ruta_inexistente_da_404(cliente):
    assert cliente.get("/pilotos/999/editar").status_code == 404


def test_web_rn002_avisa_escuderia_llena(cliente):
    # La escudería 1 (Red Bull Racing) ya tiene 2 pilotos en los datos de ejemplo
    r = cliente.post("/pilotos", data={"nombre": "Liam Lawson", "numero": "30", "nacionalidad": "Nueva Zelanda", "escuderia_id": "1"}, follow_redirects=True)
    assert "RN-002" in r.get_data(as_text=True)


def test_web_rn006_avisa_piloto_con_resultados(cliente):
    r = cliente.post("/pilotos/1/eliminar", follow_redirects=True)
    assert "RN-006" in r.get_data(as_text=True)


def test_web_crud_de_escuderia(cliente):
    cliente.post("/escuderias", data={"nombre": "Williams", "pais": "Reino Unido"})
    assert "Williams" in cliente.get("/escuderias").get_data(as_text=True)
    cliente.post("/escuderias/6/editar", data={"nombre": "Williams Racing", "pais": "Reino Unido"})
    assert "Williams Racing" in cliente.get("/escuderias").get_data(as_text=True)
    r = cliente.post("/escuderias/6/eliminar", follow_redirects=True)
    assert "Escudería eliminada" in r.get_data(as_text=True)


def test_web_registrar_resultados(cliente):
    datos = {"pos_1": "2", "pos_3": "1", "dnf_2": "1"}  # Leclerc gana, Verstappen 2.º, Pérez abandona
    r = cliente.post("/carreras/2", data=datos, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Resultados guardados" in html
    assert "DNF" in html
