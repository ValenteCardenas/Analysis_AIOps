# Analisis predictivo de fallas en arquitecturas OpenStack

## Introducción: 

En el panorama actual de la tecnología, la gestión de la infraestructura en la nube se ha vuelto demasiado compleja. Plataformas distribuidas como OpenStack permiten a las organizaciones desplegar y gestionar enormes entornos de nube, orquestando miles de máquinas virtuales, redes y sistemas de almacenamiento simultáneamente. Sin embargo, esta escala trae consigo un reto operativo significativo: cuando ocurre una falla en algún microservicio, identificar la causa raíz entre millones de líneas de logs (registros) y métricas es un proceso lento y altamente complejo para los operadores humanos.

Es para resolver este problema que surge el concepto de AIOps.

AIOps (Inteligencia Artificial para Operaciones de TI) se define como la aplicación de técnicas de ciencia de datos, estadística avanzada y aprendizaje automático (machine learning) a los grandes volúmenes de datos generados por las operaciones tecnológicas. Su propósito principal es mejorar y automatizar el monitoreo de la infraestructura, permitiendo detectar anomalías en tiempo real, predecir caídas antes de que ocurran y acelerar la resolución de problemas (pasar de una postura reactiva a una proactiva).

El presente proyecto se enmarca dentro de esta filosofía. A través del análisis de un conjunto de datos (dataset) proveniente de un entorno OpenStack sometido a inyecciones de fallas controladas, utilizaremos herramientas de estadística descriptiva e inferencial para entender cómo se comportan los distintos componentes del sistema bajo estrés. El objetivo es descubrir patrones, evaluar la propagación de errores y extraer conclusiones fundamentadas en los datos que demuestren el valor del análisis cuantitativo en la mejora de la confiabilidad de los servicios en la nube.

Teniendo esto en cuenta, podemos plantearnos las siguientes preguntas

1. Al analizar diferentes escenarios, ¿qué tipo de falla inyectada (por ejemplo, estrés de CPU vs. pérdida de paquetes en la red) genera un impacto más visible o propaga más errores a través de los distintos componentes del sistema (Nova, Neutron, Cinder)

2. ¿Existe una diferencia estadísticamente significativa en los tiempos de respuesta (latencia) de los microservicios de OpenStack cuando operan en estado normal frente a un escenario con inyección de fallas?

3. ¿Qué métricas específicas de consumo de recursos (uso de CPU, consumo de memoria, tráfico de red) presentan una mayor correlación estadística con el aumento en la severidad de los logs de error?

4. ¿Cuáles son los patrones o secuencias de logs temporales más comunes que preceden a una falla, y cómo se diferencian estadísticamente de un simple pico de carga normal en el sistema?

5. Basado en el comportamiento histórico, ¿es posible predecir el incremento en la latencia de un servicio crítico a partir del volumen y la frecuencia de los logs de advertencia (warnings) generados en los minutos previos al fallo mediante un modelo de regresión?


La elección de este tema responde a la necesidad crítica de la industria por mantener la estabilidad y disponibilidad en infraestructuras de computación en la nube modernas, donde las metodologías tradicionales de monitoreo manual ya no son viables debido a la magnitud del flujo de datos.

Lo que nos resulta particularmente interesante de este conjunto de datos es que nos ofrece una "radiografía" de un sistema bajo estrés. Al contar con registros provenientes de inyecciones de fallas controladas, no estamos analizando simples métricas estáticas, sino el comportamiento dinámico de una arquitectura en el momento exacto en que comienza a degradarse. Esto representa una oportunidad única para observar cómo se comportan los microservicios en cascada y cómo se propagan los errores entre sus distintos componentes.

A futuro, el análisis estadístico de estos datos tiene una utilidad y aplicación directa en el desarrollo de soluciones de AIOps. Si logramos identificar con precisión los patrones de falla, medir el impacto de las anomalías y anticipar la degradación de un servicio antes de que ocurra una caída total, habremos sentado las bases para diseñar sistemas de monitoreo verdaderamente proactivos. En resumen, este análisis no es solo un ejercicio numérico, sino un paso firme hacia la creación de operaciones en la nube más inteligentes, resilientes y capaces de autorepararse.



---

## 2. Obtención y Descripción de los Datos

### 2.1 Origen del Dataset

Los datos utilizados en este proyecto provienen del **Fault-Injection-Dataset**, un conjunto de datos público generado por investigadores de la Universidad Federico II de Nápoles. El dataset fue publicado como parte del artículo académico:

> Cotroneo, D., De Simone, L., Liguori, P., Natella, R., & Bidokhti, N. (2019). *How Bad Can a Bug Get? An Empirical Analysis of Software Failures in the OpenStack Cloud Computing Platform*. ESEC/FSE 2019.

### 2.2 ¿Qué contiene?

El dataset registra **911 experimentos de inyección de fallas** realizados sobre tres subsistemas críticos de OpenStack:

| Subsistema | Función en OpenStack | Núm. de Tests |
|:----------:|:---------------------|:-------------:|
| **Nova**    | Gestión de cómputo (máquinas virtuales) | 439 |
| **Cinder**  | Gestión de almacenamiento (volúmenes)   | 269 |
| **Neutron** | Gestión de redes (conectividad)         | 203 |

Cada experimento consiste en:
1. **Round 1 (faulty):** Se ejecuta un workload con una falla inyectada (mutación del código fuente).
2. **Round 2 (fault-free):** Se ejecuta el mismo workload sin falla, como grupo de control.

### 2.3 Estructura por experimento

Cada carpeta `Test_<id>` contiene:

| Archivo / Carpeta | Descripción |
|:------------------|:------------|
| `fip_info.data` | Metadatos de la falla inyectada: tipo, componente, clase y función afectada |
| `orig_file` | Código fuente original (antes de la mutación) |
| `mutated_file` | Código fuente mutado (con la falla) |
| `diff` | Diferencia entre el archivo original y el mutado |
| `logs/round_1/` | Logs del round con falla (por subsistema: nova, cinder, neutron, glance, etc.) |
| `logs/round_2/` | Logs del round sin falla (grupo de control) |
| `logs/round_1/trigger_log` | Timestamp exacto de activación de la falla |
| `logs/round_N/foreground_wl/` | Logs del workload: salida estándar y errores (assertion results) |
| `logs/round_N/trace_*.log` | Trazas distribuidas Zipkin en formato JSON |

### 2.4 Estrategia de carga

Dado que los datos crudos están distribuidos en cientos de carpetas con diferentes formatos (CSV, texto plano, JSON), la lógica de extracción y transformación se encuentra **modularizada** en `src/etl.py`. Esto permite mantener el notebook limpio y enfocado en el análisis, no en el parseo de archivos.

El módulo `etl.py` produce **dos DataFrames**:

1. **`df` (DataFrame analítico):** Una fila por experimento (911 filas). Combina los CSVs de resultados, los metadatos de inyección (`fip_info.data`), los resultados de aserción del workload y el timestamp de activación de la falla.

2. **`df_logs` (DataFrame de logs estructurados):** Una fila por línea de log parseada. Cada línea de los archivos de log de OpenStack se descompone en: `timestamp`, `pid`, `level` (severidad), `module`, `request_id` y `message`. Este parseo fue desarrollado originalmente en `notebooks/sandbox_alumno1.ipynb` e integrado al módulo ETL para reutilización.