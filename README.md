# OpenStack AIOps Project

Proyecto para análisis de trazas, logs y datasets de inyección de fallas en OpenStack.

## Estructura

```text
openstack-aiops-project/
├── .env            # Variables de entorno locales (Excluido en .gitignore)
├── .gitignore
├── pyproject.toml  # Librerías necesarias (pandas, scipy, statsmodels, seaborn, etc.)
├── uv.lock         # Lockfile estricto de dependencias autogenerado por UV
├── main.ipynb      # JUPYTER NOTEBOOK PRINCIPAL (Actúa como Main de orquestación)
├── data/
│   ├── raw/        # Versión original/cruda (Logs, Zipkin JSONs, matrices TSB)
│   └── processed/  # Tabla analítica final generada tras el ETL (.csv)
├── docs/           # Documentación general
├── notebooks/      # Espacio de experimentación / borradores individuales
│   ├── sandbox_alumno1.ipynb 
│   └── sandbox_alumno2.ipynb
└── src/
    ├── __init__.py
    ├── etl.py  # Módulo de Extracción, Limpieza y Feature Engineering
    ├── eda.py  # Módulo de Análisis Exploratorio y Dispersión
    ├── stats_testing/ # Módulo de Inferencia y Modelado Estadístico
    │   ├── __init__.py
    │   └── stats_testing.py
    └── models/ # Módulo de Regresión y Modelos de ML Futuros
        ├── __init__.py
        └── models.py
```

## `uv`

Instalar dependencias:

```bash
uv sync
```

Actualizar el lockfile:

```bash
uv lock
```

Ejecutar un comando dentro del entorno del proyecto:

```bash
uv run python --version
```

Abrir Jupyter:

```bash
uv run jupyter lab
```

Agregar una dependencia:

```bash
uv add pandas
```

Remover una dependencia:

```bash
uv remove pandas
```

## Datos

El dataset no se versiona en Git. El flujo esperado es consumir los datos desde un bucket externo de Hugging Face.

### Subir el dataset al bucket

```bash
uv tool install hf
hf auth login
hf sync ./data hf://buckets/Cesar77RR/openstack-aiops-project
```

Si quieres revisar antes de subir:

```bash
hf sync ./data hf://buckets/Cesar77RR/openstack-aiops-project --dry-run
```

### Consumirlo desde Python

Usa `hf://` con `huggingface_hub` para abrir archivos remotos sin descargarlos manualmente.

```python
import pandas as pd
from huggingface_hub import HfFileSystem

fs = HfFileSystem()
with fs.open("hf://buckets/Cesar77RR/openstack-aiops-project/Fault-Injection-Dataset/nova.tsv", "rt") as f:
    df = pd.read_csv(f, sep="\t")
```

## Notas

Los módulos `stats_testing` y `models` viven en sus respectivas carpetas para mantener el código modular y escalable.
