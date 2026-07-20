# Glosario de Dominio y Guía Conceptual: Inyección de Fallas en OpenStack (AIOps)

Este documento establece el marco teórico, los conceptos de infraestructura, la estructura del dataset y la definición del **alcance analítico de datos** para el proyecto de AIOps.

---

## Parte 1: Arquitectura de la Infraestructura (El Ecosistema Cloud)

Para comprender el origen de la telemetría y las fallas, se analiza **OpenStack**, la plataforma de cómputo en la nube de código abierto que gestiona recursos de cómputo, almacenamiento y redes en centros de datos. El proyecto se enfoca en sus tres subsistemas principales:

### Nova (OpenStack Compute)
* **Definición:** Componente central encargado de la gestión del ciclo de vida de las instancias (máquinas virtuales). Controla hipervisores (KVM/QEMU), aprovisionamiento de CPU/RAM y la planificación (*scheduling*) de recursos.
* **Contexto en el Dataset:** Incluye **439 experimentos (pruebas)**. Las fallas inyectadas evalúan impactos en la capacidad de instanciar, migrar o terminar servidores virtuales.

### Cinder (OpenStack Block Storage)
* **Definición:** Servicio de almacenamiento de bloques persistente para las instancias virtuales (equivalente a volúmenes EBS). Administra la creación, adjunto y desadjunto de discos lógicos.
* **Contexto en el Dataset:** Incluye **269 experimentos**. Las fallas inyectadas simulan errores en la asignación de volúmenes, corrupción de metadatos de almacenamiento o fallos en controladores (*drivers*) de storage.

### Neutron (OpenStack Networking)
* **Definición:** Sistema de Redes como Servicio (*NaaS*) que interconecta las interfaces de red de OpenStack. Administra topologías, enrutadores lógicos, switches virtuales, asignación de IPs flotantes y servicios DHCP.
* **Contexto en el Dataset:** Incluye **203 experimentos**. Las fallas se traducen en caídas de conectividad, degradación de enrutamiento o fallos en puertos virtuales.

---

## Parte 2: Conceptos de Fiabilidad e Ingeniería de Pruebas

### Inyección de Fallas (Fault Injection / Mutation Testing)
* **Definición:** Técnica de ingeniería de software donde se introducen deliberadamente errores o mutaciones en el código fuente para evaluar la tolerancia a fallas y la capacidad de recuperación del sistema.
* **Metodología del Dataset:** Se aplicaron mutaciones a nivel del código fuente en Python de OpenStack. En cada prueba se identifican los archivos fuente originales (`orig_file`) y mutados (`mutated_file`), la diferencia exacta (`diff`), así como los metadatos de la inyección (`fip_info.data`): componente, clase, función y punto de falla (*fault point*).

### Rondas de Ejecución (Faulty vs. Control)
Cada experimento ejecuta la misma carga de trabajo (*workload*) en dos rondas comparativas:
* **Round 1 (Faulty Round / Ronda con Falla):** Ejecución con la mutación de código **activa**. Durante el workload, la falla se dispara en la marca de tiempo registrada en `trigger_log`.
* **Round 2 (Fault-Free Round / Control Sanitario):** Ejecución del **mismo workload** pero sobre el código original y sano. Sirve como grupo de control para contrastar comportamientos normales vs. anómalos.

---

## Parte 3: Definición del Alcance de Datos del Proyecto (`src/etl.py`)

El dataset original de OpenStack contiene múltiples tipos de artefactos de telemetría (logs del sistema, logs del workload, trazas distribuidas Zipkin, parches de código y matrices de subsecuencias). 

Para garantizar un alcance claro, eficiente y alineado con los requerimientos analíticos y estadísticos del proyecto ([etapas_fases_proyecto.md](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/docs/requerimiento_proyecto/etapas_fases_proyecto.md)), el pipeline ETL implementado en [src/etl.py](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/src/etl.py) delimita el alcance estrictamente a los siguientes datos:

### Datos Dentro del Alcance (Procesados en `src/etl.py`)
1. **Resultados Maestros de Fallas (`nova.csv/tsv`, `cinder.csv/tsv`, `neutron.csv/tsv`):**
   - Registros de fallo por prueba en Round 1 y Round 2 (`round_1_failure`, `round_2_failure`).
2. **Metadatos de Inyección (`fip_info.data`):**
   - Especificación técnica de la mutación (`fault_type`, `target component`, `target class`, `target function`, `fault point`).
3. **Logs de Mensajes del Sistema (`*.log.bzip2.out`):**
   - Logs generados por los subsistemas de OpenStack (`nova`, `cinder`, `neutron`, `glance`, `keystone`, etc.) en cada ronda, estructurados mediante expresiones regulares (`PATRON_LOG`): `timestamp`, `pid`, `level` (DEBUG, INFO, WARNING, ERROR, CRITICAL, TRACE), `module`, `request_id`, `message`.
4. **Logs de Errores del Workload (`foreground_wl/*.err.log.bzip2.out`):**
   - Evaluación del impacto percibido desde la perspectiva del cliente/usuario: capturación de `assertion_result` y `error_raw`.
5. **Registro de Disparo de la Falla (`trigger_log`):**
   - Timestamp preciso (`trigger_timestamp`) del momento de activación del error inyectado en el Round 1.

### Datos Fuera del Alcance del Proyecto (Excluidos de `src/etl.py`)
* **Trazas Distribuidas Zipkin (`trace_Test_<id>_round_number` JSON):** Peticiones distribuidas y tiempos RPC inter-servicio (excluidos por volumen y complejidad no tabular).
* **Parches de Código (`orig_file`, `mutated_file`, `diff`):** Análisis de diferencias en sintaxis de código fuente.
* **Matrices Agregadas SEQ y LCS_with_VMM:** Matrices de subsecuencias de Markov precalculadas (se generan de forma propia durante la ingeniería de características a partir de los datos crudos).

---

## Parte 4: Estructura del Dataset y Variables Extraídas

### Estructura de Directorios del Dataset Crudo
```text
Fault-Injection-Dataset/
├── Nova/ (439 pruebas) | Cinder/ (269 pruebas) | Neutron/ (203 pruebas)
│   ├── Test_1/
│   │   ├── fip_info.data          (Metadatos de la mutación inyectada)
│   │   ├── orig_file / mutated_file / diff
│   │   └── logs/
│   │       ├── round_1/           (Ronda defectuosa)
│   │       │   ├── trigger_log    (Timestamp de activación de la falla)
│   │       │   ├── nova/, cinder/, neutron/, glance/ ... (*.log.bzip2.out)
│   │       │   └── foreground_wl/ (*.out.log.bzip2.out, *.err.log.bzip2.out)
│   │       └── round_2/           (Ronda de control sano)
│   │           ├── nova/, cinder/, neutron/ ... (*.log.bzip2.out)
│   │           └── foreground_wl/
├── nova.tsv / cinder.tsv / neutron.tsv (Resumen de resultados por subsistema)
```

---

## Parte 5: Mapeo de Variables y Tablas Generadas por el ETL

El archivo [src/etl.py](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/src/etl.py) transforma los datos crudos en dos DataFrames principales de Pandas:

### 1. Tabla Maestra de Análisis de Experimentos (`crear_tabla_analisis` / `limpiar_df_completo`)
Une los resultados del experimento, metadatos de mutación, logs de error del cliente y contadores agregados por nivel de log:

| Variable | Tipo de Dato | Origen / Definición Técnica | Propósito en AIOps |
| --- | --- | --- | --- |
| `test_id` | Cadena (`object`) | Identificador único del experimento (ej. `Test_1`). | Clave primaria del test. |
| `subsystem` | Categórico (`category`) | Subsistema inyectado (`Nova`, `Cinder`, `Neutron`). | Segmentación del análisis. |
| `round_1_failure` | Booleano (`bool`) | `True` si la prueba falló bajo la inyección (Round 1). | Variable objetivo / Etiqueta de falla. |
| `round_2_failure` | Booleano (`bool`) | `True` si la prueba falló en la ronda de control (Round 2). | Validación de sanidad del entorno. |
| `fault_type` | Categórico (`category`) | Cadena completa del tipo de falla inyectada. | Caracterización de la mutación. |
| `fault_origin` | Categórico (`category`) | Derivado de `fault_type`: prefijo del origen (`OPENSTACK`, `DISKIO`, `NETIO`, `URLLIB`, `URLPARSE`, `OS`, `OTRO`). | Feature Engineering de origen de falla. |
| `fault_category` | Categórico (`category`) | Derivado de `fault_type`: tipo específico sin prefijo. | Categorización detallada de la mutación. |
| `fault_target` | Categórico (`category`) | Derivado de `fault_type`: componente o recurso objetivo (ej. `VOLUME`, `INSTANCE`). | Identificación del recurso afectado. |
| `target_component` | Cadena (`object`) | Archivo fuente de OpenStack donde se realizó la mutación. | Trazabilidad del código. |
| `target_class` | Cadena (`object`) | Clase de Python mutada. | Trazabilidad del código. |
| `target_function` | Cadena (`object`) | Función de Python mutada. | Trazabilidad del código. |
| `fault_point` | Cadena (`object`) | Declaración o instrucción exacta modificada. | Punto de falla en código. |
| `assertion_result` | Categórico (`category`) | Tipo de falla detectada por las aserciones del cliente/workload (o `SIN_FALLA_DETECTADA`). | Impacto visible en el cliente. |
| `error_raw` | Cadena (`object`) | Mensaje de error completo del workload (`sin_error` si no hay). | Detalle cualitativo del error. |
| `trigger_timestamp` | Fecha/Hora (`datetime64`) | Timestamp de activación de la falla en Round 1 (con nulos permitidos en casos sin registro). | Marcador temporal de falla. |
| `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `TRACE` | Entero (`int64`) | Conteo de líneas de log generadas por nivel en Round 1. | Métricas cuantitativas de telemetría. |
| `total_log_lines` | Entero (`int64`) | Suma total de líneas de log registradas en el test. | Volumen total de actividad. |

### 2. Tabla Estructurada de Logs a Nivel Mensaje (`armar_tabla_logs` / `limpiar_logs`)
Detalla cada entrada individual de log de los servicios de OpenStack:

| Variable | Tipo de Dato | Definición Técnica |
| --- | --- | --- |
| `timestamp` | Fecha/Hora (`datetime64`) | Marca de tiempo exacta del mensaje de log. |
| `pid` | Entero (`int64`) | Identificador del proceso que generó el log. |
| `level` | Categórico (`category`) | Nivel de severidad (`INFO`, `DEBUG`, `WARNING`, `ERROR`, `CRITICAL`, `TRACE`). |
| `module` | Cadena (`object`) | Módulo interno de Python que emitió el mensaje. |
| `request_id` | Cadena (`object`) | Identificador único de la solicitud transaccional en OpenStack. |
| `message` | Cadena (`object`) | Texto crudo del mensaje de log. |
| `subsystem` | Categórico (`category`) | Subsistema evaluado (`Nova`, `Cinder`, `Neutron`). |
| `test_id` | Cadena (`object`) | Identificador de la prueba (`Test_<id>`). |
| `round_id` | Categórico (`category`) | Ronda de ejecución (`round_1` o `round_2`). |
| `log_source` | Categórico (`category`) | Componente emisor del log (`nova`, `cinder`, `neutron`, `glance`, etc.). |
| `log_file_name` | Cadena (`object`) | Archivo de origen del log. |

---

## Resumen Ejecutivo del Alcance del Proyecto

El conjunto de datos proveniente de **DessertLab** (Universidad de Nápoles Federico II) proporciona una base científica rigurosa para la ingeniería de AIOps. 

Al haber definido el alcance centrado en los datos estructurados por [src/etl.py](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/src/etl.py),

El proyecto abordará el análisis exploratorio de datos (EDA), la comparación estadística de grupos (Round 1 vs. Round 2, análisis por subsistemas y niveles de log) y las pruebas de hipótesis 
correspondientes a la guía del proyecto ([etapas_fases_proyecto.md](file:///home/cesar_r/Documentos/Proyectos/AIOps_agents/AIOps_from_analytics/Analysis_AIOps/docs/requerimiento_proyecto/etapas_fases_proyecto.md)),
 trabajando con datos limpios, reproducibles y directamente operables en Pandas.