# Pit Wall F1

Aplicación web en Python (Flask + SQLite) para gestionar una temporada de Fórmula 1: escuderías, pilotos, calendario y resultados de carreras y sprints. Con esos datos calcula sola el campeonato de pilotos y el de constructores, con los criterios de puntuación y desempate del reglamento 2026 de la FIA.

La documentación completa está en [`docs/Documentacion.pdf`](docs/Documentacion.pdf) (y su versión editable en [`docs/Documentacion.md`](docs/Documentacion.md)).

## Qué hace

| Módulo | Operaciones |
|---|---|
| Escuderías | Alta, consulta, edición y baja |
| Pilotos | Alta, consulta, edición (escudería, activo o reserva) y baja |
| Calendario | Alta, consulta, edición y baja de eventos, con o sin sprint |
| Resultados | Registrar o corregir la clasificación de cada carrera y cada sprint, con la distancia que completó el líder |
| Campeonato | Tabla de pilotos y de constructores, calculada con los resultados |

## Datos de la temporada 2026

Al arrancar por primera vez carga la temporada 2026 real: 11 escuderías, los 25 pilotos que han corrido, el calendario de 23 eventos (6 con sprint) y la clasificación completa de las 20 carreras y 6 sprints corridos hasta el GP de Brasil (8 de noviembre de 2026).

Los datos están en [`app/datos_2026.json`](app/datos_2026.json) y vienen de la [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) (la continuación de Ergast), consultada el 21 de noviembre de 2026. El campeonato que calcula la aplicación coincide con el oficial en puntos y en orden, incluidos los empates.

## Reglas de negocio

Están programadas en [`app/reglas.py`](app/reglas.py) y documentadas, con su artículo del reglamento, en la [documentación](docs/Documentacion.md). Cuando una operación no las cumple, la pantalla avisa y no guarda nada.

| Clave | Regla | Reglamento FIA 2026 |
|---|---|---|
| RN-001 | Puntos de carrera según la distancia que completó el líder; con 75 % o más: 25-18-15-12-10-8-6-4-2-1 | A2.2.1 |
| RN-002 | Puntos de sprint: 8-7-6-5-4-3-2-1 si el líder completó al menos el 50 % | A2.2.2 |
| RN-003 | Solo suman los clasificados: abandono, no salió, descalificado o no clasificado no llevan posición ni puntos | A2.2.1 |
| RN-004 | Cada escudería corre con 2 autos: máximo 2 pilotos activos y 2 pilotos por sesión | A2.1.3 |
| RN-005 | Máximo 4 pilotos distintos por escudería en la temporada | B1.7.1 |
| RN-006 | Número de piloto único, entre 1 y 99 | — |
| RN-007 | En cada sesión, un resultado por piloto y posiciones seguidas desde el 1.º, sin repetir | — |
| RN-008 | Solo se registran resultados de eventos ya corridos; el sprint, solo en fines de semana con sprint | — |
| RN-009 | Campeonato de pilotos: suma de carreras y sprints; en empate, más 1.os lugares en carreras, luego más 2.os, y así sucesivamente | A2.1.4 |
| RN-010 | Campeonato de constructores: suma de los dos autos, con la escudería con la que corrió cada piloto en ese evento; mismo desempate | A2.1.4 |
| RN-011 | No se elimina un piloto con resultados ni una escudería con pilotos o resultados | — |

## Ejecutar en local

Requiere Python 3.11 o más reciente.

```bash
python -m venv .venv
source .venv/bin/activate            # En Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
flask --app app run                  # http://127.0.0.1:5000
```

La base de datos se crea sola en `instance/pitwall.db`. Para volver a los datos originales, borra ese archivo.

## Pruebas

```bash
pytest                       # todas (43)
pytest -k rn -v              # solo las de reglas de negocio
```

## Desplegar en Render (gratis)

1. Sube este proyecto a un repositorio de GitHub.
2. Entra a [render.com](https://render.com), inicia sesión con GitHub y elige **New + → Blueprint**.
3. Selecciona el repositorio. Render lee [`render.yaml`](render.yaml) y crea el servicio web.
4. Al terminar el despliegue, Render da una dirección pública del tipo `https://f1-pitwall.onrender.com`.

En el plan gratuito el disco no es permanente: cuando el servicio se reinicia, la base de datos vuelve a los datos de la temporada. Si ya estaba desplegado, Render vuelve a desplegar solo cada vez que se sube un cambio al repositorio.

### Variables de entorno

| Variable | Para qué | Valor por defecto |
|---|---|---|
| `SECRET_KEY` | Firma de los mensajes de la sesión | Una clave de desarrollo |
| `DATABASE` | Ruta del archivo SQLite | `instance/pitwall.db` |
| `DATOS_EJEMPLO` | `1` carga la temporada 2026 si la base está vacía; `0` arranca vacía | `1` |

## Estructura

```
app/
  __init__.py       create_app(): configuración de Flask
  db.py             tablas SQLite y carga de la temporada
  datos_2026.json   temporada 2026 (escuderías, pilotos, calendario y resultados)
  reglas.py         reglas de negocio (toda escritura pasa por aquí)
  rutas.py          pantallas y formularios
  templates/        HTML (Jinja2)
  static/           estilos
tests/
  test_reglas.py    pruebas de cada regla (test_rn###_...)
  test_web.py       pruebas de las pantallas
docs/               documentación y capturas
render.yaml · Procfile
```

Proyecto escolar sin relación oficial con la Fórmula 1, la FIA ni las escuderías.
