# Guía y Requerimientos del Proyecto Final: Etapas y Fases

Este documento consolida la estructura por etapas y los requerimientos técnicos y metodológicos para el desarrollo, evaluación y presentación del proyecto final.

---

## Etapas del Proyecto

### 1. Limpieza y Preparación de Datos (ETL)
Etapa inicial donde se preparan los datos crudos para el análisis:
- **Manejo de valores nulos (NaN):** Decisión y justificación explícita de eliminación de filas o imputación de valores (media, mediana, etc.).
- **Eliminación de duplicados y datos irrelevantes:** Limpieza de registros repetidos y filtrado de errores o valores anómalos de registro (p. ej., códigos no válidos en encuestas).
- **Conversión de tipos de datos adecuados:** Garantizar la correcta tipificación de variables (numéricas a `int`/`float`, fechas a `datetime`, categorías a `category`).
- **Creación de nuevas variables (Feature Engineering):** Generar columnas derivadas según la necesidad del análisis (p. ej., extracción de agregados, categorización ordinal o variables de estado).
- **Documentación:** Explicar y justificar cada paso del proceso ETL.

---

### 2. Análisis Exploratorio de Datos (EDA) y Estadística Descriptiva
Exploración preliminar para entender el comportamiento y distribución de las variables:
- **Estadística descriptiva:** Cálculo de medidas de tendencia central (media, mediana, moda) y de dispersión (varianza, desviación estándar, rango, IQR).
- **Análisis de correlación:** Identificar relaciones inter-variable mediante matrices y mapas de calor (*heatmap*).
- **Visualización de datos:** Gráficos estáticos claros y bien etiquetados (`matplotlib`, `seaborn` o `plotly`):
  - Histogramas y gráficos de densidad (KDE).
  - Boxplots (diagramas de caja) para detección de outliers.
  - Scatter plots / Pairplots, mapas de calor, etc. según aplique.

---

### 3. Pruebas de Hipótesis y Normalidad (Fundamentación)
Someter las variables numéricas a evaluación estadística formal para justificar las técnicas de modelado posteriores:
- **Pruebas de normalidad:** Shapiro-Wilk, Kolmogorov-Smirnov, acompañados de análisis visual (gráficos Q-Q y KDE) para determinar si la distribución es normal o sesgada.
- **Estimación con Bootstrap:** Remuestreo para obtener intervalos de confianza de estadísticos clave (p. ej., mediana o media en distribuciones no normales).
- **Pruebas de significancia preliminares:** Comparación inicial de grupos según la distribución de datos (Prueba T, ANOVA, Kruskal-Wallis, Mann-Whitney).

---

### 4. Modelado Estadístico (Selección del Enfoque)
Punto de convergencia técnica donde se formaliza el enfoque metodológico de análisis:
- En función de la naturaleza de los datos y las preguntas de investigación, se define si el proyecto se enfoca en comparación de grupos (pruebas paramétricas/no paramétricas) y/o modelado predictivo/explicativo (regresión).

---

### 5. Modelado  estadistico y pruebas de hipótesis
- **Requisito Principal (Obligatorio):**
  - Aplicación de al menos una técnica de comparación de grupos o prueba de hipótesis según la naturaleza de los datos.
  - **Opciones:** Pruebas paramétricas o no paramétricas para comparación de medias/medianas (p. ej., *t-Test*, *ANOVA*, *Kruskal-Wallis*, *Mann-Whitney*) o estimación de parámetros mediante **intervalos de confianza con Bootstrap**.
- **Requisito Adicional (Opcional / Deseable):**
  - Si las características de los datos lo permiten y se busca robustecer el análisis, se sugiere complementar aplicando un **modelo de regresión lineal** (simple o múltiple).

---

### 6. Evaluación del Modelo y Supuestos
- **Validación de Supuestos:**
  - Según la técnica elegida, evaluar los supuestos básicos correspondientes (p. ej., linealidad, homocedasticidad, normalidad de residuos, ausencia de multicolinealidad/VIF en regresión múltiple).
  - *En caso de incumplimiento:* Reportar el resultado obtenido, documentar claramente qué supuestos no se cumplen y detallar el impacto que esto tiene en la validez del análisis.
  
- **Impacto**: Si un supuesto no se cumple (ej. los residuos no son normales), se debe anotar cuál fue el impacto en el modelo
- **Métricas de Rendimiento y Reporte Estadístico:**
  - Reportar métricas pertinentes según la técnica empleada: *p-valores*, estadísticos de prueba ($t$, $F$, $H$), intervalos de confianza.
  - En caso de regresión: reportar $R^2$, $R^2$ ajustado, MAE y RMSE.
- **Análisis Complementarios (Opcionales y bajo justificación técnica):**
  - Técnicas de Clasificación (p. ej., Regresión Logística, Árboles).
  - Técnicas de Clustering (Agrupamiento, p. ej., K-Means).
  - Dashboard interactivo creado con `Dash` (de incluirse, debe utilizarse activamente en la exposición).
  - Otras técnicas avanzadas adicionales.

---

### 7. Conclusiones
- **Interpretación de Resultados:** Explicar el significado práctico y analítico de los hallazgos del modelo o pruebas estadísticas.
- **Respuesta a Preguntas de Investigación:** Responder de manera directa a los objetivos y preguntas planteadas al inicio del proyecto.
- **Limitaciones y Trabajo Futuro:** Identificar supuestos no cumplidos, sesgos o fallas detectadas, junto con propuestas de mejora o líneas futuras de investigación.

---

### 8. Presentación de Resultados y Entregables
- **Jupyter Notebook:** Debe estar limpio, reproducible y estructurado con celdas Markdown que expliquen paso a paso la lógica, código e interpretación.
- **Visualizaciones:** Gráficos de calidad profesional con títulos, etiquetas en ejes y leyendas claras.
- **Material de Respaldo:** Versión exportada del Notebook en formato PDF o HTML.
- **Presentación Oral:** Exposición clara y concisa respetando los tiempos asignados. Cada integrante del equipo debe participar para su evaluación individual.
- **Soporte Interactivo (Opcional):** Uso del Dashboard en `Dash` como apoyo visual durante la defensa oral.