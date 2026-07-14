# Glosario de Dominio y Guía Conceptual: Inyección de Fallas en OpenStack (AIOps)

## Parte 1: Arquitectura de la Infraestructura (El Ecosistema Cloud)

Para entender de dónde salen los datos, primero se debe comprender **OpenStack**, el sistema operativo de nube de código abierto que gestiona pools de cómputo, almacenamiento y redes en grandes centros de datos. El dataset se centra en sus tres pilares esenciales:

### Nova (OpenStack Compute)

* **Definición:** Es el componente central encargado de la gestión de instancias (máquinas virtuales) en la nube. Controla el ciclo de vida de los hipervisores (como KVM/QEMU), el aprovisionamiento de CPU, memoria RAM y el agendamiento (scheduling) de dónde debe correr una carga de trabajo.
* **Contexto en el dataset:** Cuenta con **439 pruebas** dedicadas. Si una falla se inyecta en Nova, lo lógico es observar si impacta la capacidad de lanzar, suspender o destruir instancias de cómputo.

### Cinder (OpenStack Block Storage)

* **Definición:** Es el servicio que proporciona almacenamiento de bloques persistente a las instancias virtuales (equivalente a los discos EBS en AWS). Permite crear, adjuntar y desadjuntar volúmenes a los servidores lógicos de Nova.
* **Contexto en el dataset:** Cuenta con **269 pruebas**. Las fallas inyectadas aquí simulan bugs de software en la asignación de storage, corrupción en metadatos de volúmenes o fallos de comunicación con los drivers de almacenamiento.

### Neutron (OpenStack Networking)

* **Definición:** Es el sistema encargado de proveer "Redes como Servicio" (NaaS) entre interfaces de dispositivos administrados por otros servicios de OpenStack (como Nova). Gestiona topologías de red, switches virtuales, enrutadores lógicos, IPs flotantes, DHCP y balanceadores de carga.
* **Contexto en el dataset:** Cuenta con **203 pruebas**. Las fallas aquí se traducen en problemas de conectividad, caída de routers lógicos o fallas en el mapeo de puertos virtuales de red.

---

## Parte 2: Conceptos de Fiabilidad e Ingeniería de Pruebas

### Inyección de Fallas (Fault Injection / Mutation Testing)

* **Definición:** Técnica de pruebas de software robusta que introduce deliberadamente errores lógicos o excepciones en el código fuente de un sistema para observar cómo reacciona y evaluar su tolerancia a fallas.
* **Metodología del Dataset:** Los autores aplicaron *mutaciones* a nivel de código de Python (OpenStack está escrito principalmente en Python). Alteraron sentencias dentro de archivos fuentes específicos (`orig_file` vs `mutated_file`), modificando operadores condicionales, omitiendo llamadas a métodos o alterando el retorno de funciones críticas. El resultado de estas mutaciones genera el archivo `diff` presente en cada test.

### Rounds de Ejecución (Fallas vs. Control Sanitario)

Para poder hacer ciencia de datos rigurosa y comparar grupos, los experimentos ejecutan la misma carga de trabajo bajo dos condiciones controladas:

* **Round 1 (Faulty Round):** La ejecución del workload con la mutación de código **activa**. En el momento indicado por el archivo `trigger_log`, el código defectuoso es ejecutado por el sistema.
* **Round 2 (Fault-Free Round / Control):** La ejecución del **mismo workload** pero con el código original, completamente sano. Actúa como el grupo de control estadístico para limpiar el "ruido de fondo" operacional de la infraestructura.

---

## Parte 3: Telemetría y Formatos de Datos Analíticos

### Traza Distribuida (Distributed Trace)

* **Definición:** En una arquitectura de microservicios o sistemas distribuidos como OpenStack, una petición del usuario (ej. *"crear una máquina virtual con un volumen adjunto"*) pasa por decenas de subsistemas, APIs e hilos de ejecución distintos. Una traza es el mapa completo del viaje que hace esa petición a lo largo de toda la infraestructura.

### Zipkin

* **Definición:** Es una herramienta de código abierto de rastreo distribuido (*distributed tracing system*). Ayuda a recopilar los datos de temporización necesarios para solucionar problemas de latencia en arquitecturas de microservicios.
* **El archivo JSON de trazas:** Recopila cada mensaje, llamada RPC o petición HTTP interna enviada entre componentes de OpenStack durante la prueba. Cada llamada contiene identificadores únicos (`traceId`, `spanId`), marcas de tiempo exactas y relaciones de parentesco (*parentspans*), permitiéndoles mapear y contar con precisión variables de red complejas como la longitud de traza o la cantidad de llamadas remotas hechas por segundo.

### Matrices SEQ y LCS_with_VMM

Son archivos agregados en formato TSV (*Tab-Separated Values*) que representan los experimentos de forma matricial condensada:

* **SEQ (Sequences):** Convierte las secuencias temporales de logs y eventos de ejecución de cada test en representaciones numéricas o tokens ordenados secuencialmente. Permite analizar si el *orden cronológico* de los eventos es un predictor de fallas.
* **LCS with VMM (Longest Common Subsequence with Variable Memory Markov):** Aplica técnicas de minería de secuencias para encontrar la subsecuencia común más larga entre los logs anormales y los logs sanos, utilizando modelos de Markov para identificar patrones probabilísticos de propagación de errores.

---

## Parte 4: Mapeo de Variables para la Tabla Analítica (Del Raw a Pandas)

Al procesar la versión cruda en su ETL, deberán derivar registros estructurados que combinen variables categóricas de metadatos y numéricas obtenidas mediante el parseo de los JSONs de Zipkin y logs:

| Concepto de Datos | Variable en el Dataset | Tipo de Variable | Significado Técnico para AIOps |
| --- | --- | --- | --- |
| **Component/Class/Function** | Categórica | Especifica exactamente el fragmento de código de OpenStack que fue saboteado mediante la mutación. |  |
| **Fault_Type** | Categórica | El tipo de bug inducido (omisión de asignación, error condicional, etc.). |  |
| **API Error / Assertion** | Categórica / Booleana | Indica si el workload detectó un fallo explícito a nivel de interfaz de usuario o si tronó un chequeo interno de sanidad. |  |
| **Longitud de Traza** | Numérica (Derivada) | Conteo total de operaciones/mensajes registrados en el JSON de Zipkin. |  |
| **Número de Subsistemas** | Numérica (Derivada) | Cantidad de componentes únicos de OpenStack (Nova, Cinder, Neutron, Glance, Keystone) involucrados en la traza. |  |
| **Métricas de Anomalías** | Numérica (Derivada) | Recuento diferencial de eventos extraños en logs de Round 1 en comparación al patrón base del Round 2. |  |

---

## Resumen Ejecutivo de Comprensión del Dataset (Para la entrega)

Este conjunto de datos proviene del prestigioso grupo de investigación **DessertLab** (Universidad de Nápoles Federico II, Italia) y fue recolectado bajo entornos controlados de inyección de fallas en la nube de producción académica.

Su valor reside en que **no es un dataset de juguete ni pre-resuelto**. Demuestra la complejidad real de AIOps: la infraestructura de nube es ruidosa por naturaleza; por lo tanto, un bug de software inyectado en el almacenamiento (Cinder) puede propagarse silenciosamente a través de la red (Neutron) y manifestarse como una anomalía de tiempo de espera en el cómputo (Nova). La meta estadística de ustedes será aislar este ruido y encontrar los patrones matemáticos en los logs y trazas distribuidas que delatan las fallas antes de que colapsen el sistema operativo cloud.