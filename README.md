# Pit Wall F1

Aplicación web en Python (Flask + SQLite) para gestionar una temporada de Fórmula 1: escuderías, pilotos, carreras y resultados. Con esos datos calcula sola el campeonato de pilotos y el de constructores.

La documentación completa está en [`docs/Documentacion.pdf`](docs/Documentacion.pdf) (y su versión editable en [`docs/Documentacion.md`](docs/Documentacion.md)).

## Qué hace

| Módulo | Operaciones |
|---|---|
| Escuderías | Alta, consulta, edición y baja |
| Pilotos | Alta, consulta, edición (incluye cambio de escudería) y baja |
| Carreras | Alta, consulta, edición y baja del calendario |
| Resultados | Registrar o corregir las posiciones y abandonos (DNF) de cada carrera |
| Campeonato | Tabla de pilotos y de constructores, calculada con los resultados |

Al arrancar por primera vez carga datos de ejemplo: 5 escuderías y 10 pilotos de la temporada 2024, 4 carreras del calendario 2024 y el resultado real del GP de Baréin 2024 (top 10).

## Reglas de negocio

Están programadas en [`app/reglas.py`](app/reglas.py) y cada una tiene pruebas en [`tests/test_reglas.py`](tests/test_reglas.py) con su clave en el nombre (por ejemplo, `test_rn002_...`). Cuando una operación incumple una regla, la pantalla muestra el aviso con su clave (por ejemplo, «RN-002 · La escudería ya tiene 2 pilotos.»).

| Clave | Regla |
|---|---|
| RN-001 | Puntos 25-18-15-12-10-8-6-4-2-1 del 1.º al 10.º lugar; del 11.º en adelante y los abandonos no suman |
| RN-002 | Máximo 2 pilotos por escudería |
| RN-003 | Número de piloto único, entre 1 y 99 |
| RN-004 | En una carrera, un resultado por piloto y una posición por piloto, consecutivas desde el 1.º |
| RN-005 | No se registran resultados de carreras con fecha futura |
| RN-006 | No se elimina un piloto con resultados ni una escudería con pilotos |
| RN-007 | El campeonato se ordena por puntos; en empate, más victorias y luego más segundos lugares |

## Ejecutar en local

Requiere Python 3.11 o más reciente.

```bash
python -m venv .venv
source .venv/bin/activate            # En Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
flask --app app run --debug          # http://127.0.0.1:5000
```

La base de datos se crea sola en `instance/pitwall.db`. Para empezar de cero, borra ese archivo.

## Pruebas

```bash
pytest                       # todas (28)
pytest -k rn -v              # solo las de reglas de negocio
```

## Desplegar en Render (gratis)

1. Sube este proyecto a un repositorio de GitHub.
2. Entra a [render.com](https://render.com), inicia sesión con GitHub y elige **New + → Blueprint**.
3. Selecciona el repositorio. Render lee [`render.yaml`](render.yaml) y crea el servicio web.
4. Al terminar el despliegue, Render da una dirección pública del tipo `https://f1-pitwall.onrender.com`.

En el plan gratuito el disco no es permanente: cuando el servicio se reinicia, la base de datos vuelve a los datos de ejemplo. Para una demo esto no es problema.

Otras plataformas que lean un `Procfile` (Railway, Heroku) sirven igual; el comando de arranque es `gunicorn "app:create_app()"`.

### Variables de entorno

| Variable | Para qué | Valor por defecto |
|---|---|---|
| `SECRET_KEY` | Firma de los mensajes de la sesión | Una clave de desarrollo |
| `DATABASE` | Ruta del archivo SQLite | `instance/pitwall.db` |
| `DATOS_EJEMPLO` | `1` carga los datos de ejemplo si la base está vacía; `0` arranca vacía | `1` |

## Estructura

```
app/
  __init__.py      create_app(): configuración de Flask
  db.py            tablas SQLite y datos de ejemplo
  reglas.py        reglas de negocio (toda escritura pasa por aquí)
  rutas.py         pantallas y formularios
  templates/       HTML (Jinja2)
  static/          estilos
tests/
  test_reglas.py   pruebas de cada regla RN-###
  test_web.py      pruebas de las pantallas
docs/              documentación y capturas
render.yaml · Procfile
```

Proyecto escolar sin relación oficial con la Fórmula 1, la FIA ni las escuderías.
