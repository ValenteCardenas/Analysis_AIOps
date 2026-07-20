# Reporte y Documentación Técnica: Etapa 1 - Limpieza y Preparación de Datos (ETL)

## 1. Introducción y Alcance del Procesamiento ETL

La primera etapa del proyecto consiste en la extracción, transformación y carga (ETL) de los datos crudos del **OpenStack Fault-Injection Dataset** (proveniente de *DessertLab*, Universidad de Nápoles Federico II).

El procesamiento se implementó de forma modular y reproducible en el módulo [`src/etl.py`](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/src/etl.py).

### Alcance de Datos Considerados
El pipeline procesa los 911 experimentos de inyección de fallas divididos en los tres subsistemas centrales de OpenStack:
* **Nova (Compute):** 439 pruebas (`Test_1` a `Test_439`).
* **Cinder (Block Storage):** 269 pruebas.
* **Neutron (Networking):** 203 pruebas.

Se extrajeron y consolidaron 5 fuentes de datos crudos:
1. **Archivos Maestros de Fallas (`nova.csv/tsv`, `cinder.csv/tsv`, `neutron.csv/tsv`):** Resultados globales del experimento.
2. **Metadatos de la Inyección (`fip_info.data`):** Información técnica de la mutación en código.
3. **Logs del Sistema de OpenStack (`*.log.bzip2.out`):** Mensajes emitidos por `nova`, `cinder`, `neutron`, `glance`, `keystone`, etc.
4. **Logs del Cliente/Workload (`foreground_wl/*.err.log.bzip2.out`):** Mensajes de aserciones y errores durante la ejecución del workload.
5. **Registro de Disparo de Falla (`trigger_log`):** Marca temporal de la activación de la mutación en Round 1.

---

## 2. Análisis del Cumplimiento de los Requerimientos del Proyecto

A continuación se detalla cómo se cubrió cada punto exigido en la **Etapa 1 (Limpieza y Preparación de Datos)** de la guía del proyecto ([etapas_fases_proyecto.md](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/docs/requerimiento_proyecto/etapas_fases_proyecto.md)):

### A. Manejo de Valores Nulos (NaN)
* **Resultado del Análisis Empírico:**
  - En la tabla de análisis cruda (`crear_tabla_analisis`), se identificaron:
    - `assertion_result`: 643 valores nulos.
    - `error_raw`: 431 valores nulos.
    - `trigger_timestamp`: 473 valores nulos.
* **Estrategia y Justificación:**
  - **`assertion_result`:** Se imputaron los nulos con la etiqueta categórica `"SIN_FALLA_DETECTADA"`. *Justificación:* La ausencia de registro en las aserciones del cliente indica que el workload se completó sin detectar una falla explícita a nivel de interfaz de usuario.
  - **`error_raw`:** Se imputó con el valor `"sin_error"`. *Justificación:* Facilita el filtrado en Pandas sin perder registros en operaciones de agrupación.
  - **`trigger_timestamp`:** Se preservó como `NaT` (*Not a Time*). *Justificación:* En pruebas donde la falla no llegó a activarse o en ejecuciones de control, la fecha de disparo simplemente no existe. Eliminar estas filas sesgaría el dataset borrando pruebas sanas de control.

### B. Eliminación de Duplicados y Datos Irrelevantes
* **Resultado del Análisis Empírico:**
  - En la tabla maestra de pruebas (`crear_tabla_analisis` / `limpiar_df_completo`): 0 filas duplicadas a nivel experimento (911/911 registros únicos).
  - En la tabla de logs detallados (`armar_tabla_logs` / `limpiar_logs`): Se detectaron y eliminaron duplicados exactos (ejemplo: 78 líneas duplicadas en una muestra de 5 pruebas) basándose en la tupla `['timestamp', 'pid', 'level', 'module', 'message', 'test_id', 'round_id']`.
* **Filtros de Exclusión / Datos Irrelevantes:**
  - Se omitió la subcarpeta `foreground_wl` durante el conteo y estructuración de los logs de componentes para evitar la duplicación con la actividad del workload cliente.
  - Se omitieron archivos corruptos o de 0 bytes aplicando bloques `try-except` con manejo explícito de codificación (`errors="ignore"` / `errors="replace"`).

### C. Conversión a Tipos de Datos Adecuados
* **Transformaciones Aplicadas:**
  - **Categorías (`category`):** `subsystem` (3 categorías), `fault_type` (34 tipos), `assertion_result` (5 categorías), `fault_origin` (6 orígenes), `fault_category` (5 categorías), `fault_target` (13 objetivos), `level` (6 niveles: DEBUG, INFO, WARNING, ERROR, CRITICAL, TRACE), `round_id` (round_1, round_2), `log_source`.
  - **Fechas (`datetime64[us]`):** `trigger_timestamp` y `timestamp` de logs mediante `pd.to_datetime` con formato explícito `%Y-%m-%d %H:%M:%S.%f`.
  - **Booleanos (`bool`):** `round_1_failure` y `round_2_failure` estandarizando valores heterogéneos (`"yes"`/`"no"`, `"failure"`/`"no_failure"`, `"true"`/`"false"`).
  - **Enteros (`int64`):** Conteo de logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `TRACE`, `total_log_lines`) y `pid`.
* **Justificación Técnica:**
  - Reducción drástica del uso de memoria RAM (optimización del uso de Pandas).
  - Adecuación de variables categóricas para fases posteriores de codificación (*One-Hot Encoding* / *Target Encoding*) y modelos estadísticos (ANOVA, Regresión).
  - Habilitación de cálculos de diferencia de tiempo (*timestamps*).

### D. Creación de Nuevas Variables (Feature Engineering)
Se crearon **10 variables derivadas** esenciales para el análisis de AIOps:
1. **`fault_origin` (Categoría):** Extrae el prefijo del origen del fallo (`OPENSTACK`, `DISKIO`, `NETIO`, `URLLIB`, `URLPARSE`, `OS`, `OTRO`). Permite evaluar la hipótesis de si las fallas del sistema operativo o de red tienen mayor tasa de propagación que las fallas internas de OpenStack.
2. **`fault_category` (Categoría):** Tipo específico de mutación lógica (ej. `MISSING_FUNCTION_CALL`, `WRONG_RETURN_VALUE`).
3. **`fault_target` (Categoría):** Componente o recurso objetivo afectado (`VOLUME`, `INSTANCE`, `NETWORK`, `IMAGE`, `SSH`, etc.).
4. **Conteos Cuantitativos por Nivel de Log (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `TRACE`):** Métricas de intensidad de la telemetría durante la ejecución defectuosa (Round 1).
5. **`total_log_lines` (Entero):** Suma total de registros de log generados durante la prueba. Permite evaluar si las fallas generan tormentas de logs (*log floods*).

---

## 3. Salida Empírica de las Funciones (`src/etl.py`)

Tras ejecutar las funciones mediante `uv run python`, se obtuvieron los siguientes resultados empíricos:

### A. Tabla Maestra de Análisis (`crear_tabla_analisis` + `limpiar_df_completo`)
* **Dimensión Final:** 911 filas × 22 columnas.
* **Resumen de Nulos Finales:** 0 nulos en todas las columnas categóricas, booleanas y numéricas. Únicamente 473 nulos en `trigger_timestamp` (justificados por ausencia de disparo en pruebas no activadas o controles).

#### Estructura de Columnas Generadas:
```text
Columns (22):
- test_id (str)
- round_1_failure (bool)
- round_2_failure (bool)
- subsystem (category: ['Cinder', 'Neutron', 'Nova'])
- fault_type (category: 34 tipos de fallas)
- target_component (str)
- target_class (str)
- target_function_def (str)
- fault_point (str)
- assertion_result (category: 5 resultados)
- error_raw (str)
- trigger_timestamp (datetime64[us])
- DEBUG, INFO, WARNING, ERROR, CRITICAL, TRACE (int64)
- total_log_lines (int64)
- fault_origin (category: 6 orígenes)
- fault_category (category: 5 categorías)
- fault_target (category: 13 recursos objetivos)
```

### B. Tabla de Logs Detallados (`armar_tabla_logs` + `limpiar_logs`)
* **Muestra de Evaluación (5 pruebas):** 246,278 líneas de log procesadas y limpiadas.
* **Duplicados Eliminados:** 78 líneas repetidas exactas borradas.
* **Ordenamiento:** Cronológico exacto por `timestamp`.

---

## 4. Evaluación de Cobertura y Aspectos a Considerar en Fases Posteriores

### Aspectos 100% Cubiertos:
- Manejo e imputación de nulos justificada.
- Desduplicación a nivel test y a nivel mensaje de log.
- Conversión estricta de tipos de datos (`bool`, `datetime`, `category`, `int64`).
- Creación de variables agrupadas y desglosadas por origen, categoría y conteos cuantitativos.
- Automatización e impresion de mensajes informativos de progreso.

### Aspectos a Considerar para la Fase de Modelado (No requeridos en ETL):
- **Escalamiento/Normalización de Variables:** Las columnas de conteo (`total_log_lines`, `DEBUG`, `INFO`, etc.) presentan alta dispersión. Se mantienen en escala natural para el análisis exploratorio (EDA) y pruebas no paramétricas (Kruskal-Wallis / Mann-Whitney), y deberán escalarse (*StandardScaler* o *RobustScaler*) únicamente en la fase de modelado predictivo.
- **Tratamiento de Outliers Extremos:** No se eliminan pruebas con conteos extremos de logs durante el ETL para no sesgar la caracterización real del comportamiento anómalo en AIOps.

---

## 5. Conclusión de la Etapa ETL

La Etapa 1 queda **completamente cubierta y validada empíricamente**. El código de [`src/etl.py`](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/src/etl.py) transforma eficientemente datos crudos desestructurados y fragmentados en dos estructuras tabulares limpias, robustas y optimizadas para las etapas subsecuentes de EDA, Pruebas de Hipótesis y Modelado.
