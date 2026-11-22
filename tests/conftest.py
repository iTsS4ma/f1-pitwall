import pytest

from app import create_app
from app.db import conectar, crear_tablas


@pytest.fixture
def conn(tmp_path):
    """Base de datos vacía (sin datos de ejemplo) para probar las reglas."""
    c = conectar(str(tmp_path / "prueba.db"))
    crear_tablas(c, datos_ejemplo=False)
    yield c
    c.close()


@pytest.fixture
def cliente(tmp_path):
    """Aplicación web con los datos de ejemplo."""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "web.db"), "DATOS_EJEMPLO": True})
    return app.test_client()
