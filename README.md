# OpenStack AIOps Project

Proyecto para análisis de trazas, logs y datasets de inyección de fallas en OpenStack.

## Estructura

```text
openstack-aiops-project/
├── .env
├── .gitignore
├── pyproject.toml
├── uv.lock
├── main.ipynb
├── data/
│   ├── raw/
│   └── processed/
├── docs/
├── notebooks/
│   ├── sandbox_alumno1.ipynb
│   └── sandbox_alumno2.ipynb
└── src/
    ├── __init__.py
    ├── etl.py
    ├── eda.py
    ├── stats_testing/
    │   ├── __init__.py
    │   └── stats_testing.py
    └── models/
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
