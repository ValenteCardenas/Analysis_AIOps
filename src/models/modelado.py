import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import shapiro
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor

def preparar_datos_modelo(df_limpio: pd.DataFrame, df_logs_limpio: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    if imprimir_mensajes:
        print("[Modelado] Agrupando los logs por prueba y por round...")
        
    # Vamos a contar cuantos logs de cada nivel hay por cada prueba y round
    conteo_logs = df_logs_limpio.groupby(['subsystem', 'test_id', 'round_id', 'level'], observed=False).size().unstack(fill_value=0)
    conteo_logs = conteo_logs.reset_index()
    
    # Nos interesan principalmente los WARNINGS y ERRORS
    # A veces CRITICAL puede aparecer, asi que lo sumamos a los errores si existe
    if 'CRITICAL' in conteo_logs.columns:
        conteo_logs['ERROR_TOTAL'] = conteo_logs['ERROR'] + conteo_logs['CRITICAL']
    else:
        conteo_logs['ERROR_TOTAL'] = conteo_logs['ERROR'] if 'ERROR' in conteo_logs.columns else 0
        
    if 'WARNING' not in conteo_logs.columns:
        conteo_logs['WARNING'] = 0

    columnas_nivel = [c for c in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'TRACE'] if c in conteo_logs.columns]
    conteo_logs['total_log_lines'] = conteo_logs[columnas_nivel].sum(axis=1)
        
    # Ahora vamos a cruzar esta info con la metadata de las fallas
    # Queremos saber el subsistema y el origen de la falla
    columnas_metadata = ['test_id', 'subsystem', 'fault_origin', 'fault_category']
    df_modelo = pd.merge(conteo_logs, df_limpio[columnas_metadata], on=['test_id', 'subsystem'], how='inner')
    
    if imprimir_mensajes:
        print(f"[Modelado] Listo. Tenemos un dataset con {len(df_modelo)} filas.")
        
    return df_modelo

'''
 Mira César, aquí tenemos de dos sopas, hacemos la prueba de sí ocurrió o no una falla o cuántas
 Ahorita lo hice en el enfoque de que si ocurrió o no
 Para hacerla de cuántas tendríamos que usar otro modelo como WRS (Wilcoxon Rank-Sum) o Mann-Whitney U
 Pero el problema es que no todos los subsistemas tienen los mismos datos para hacer la prueba
 Por lo que lo hice mejor en el enfoque de que si ocurrió o no
'''

def prueba_hipotesis_errores(df_modelo: pd.DataFrame, imprimir_mensajes: bool = True) -> dict:
    """
    Prueba de hipotesis (Chi-Cuadrada) para comparar si la proporcion de pruebas con errores
    es diferente entre el Round 1 vs Round 2.
    - H0 (Nula): La aparicion de errores es independiente del round.
    - H1 (Alternativa): Hay dependencia (el round afecta si hay errores o no).
    """
    if imprimir_mensajes:
        print("\n" + "="*50)
        print("PRUEBA DE HIPOTESIS (CHI-CUADRADA)")
        print("="*50)
        
    # Creamos una columna temporal que dice si hubo error o no (True/False)
    # Como Chi-Cuadrada ocupa categorias, convertimos el conteo a un "Si falló / No falló"
    df_temp = df_modelo.copy()
    df_temp['tuvo_error'] = df_temp['ERROR_TOTAL'] > 0
    
    # Armamos la tabla de contingencia cruzando el round con la columna de tuvo_error
    tabla_contingencia = pd.crosstab(df_temp['round_id'], df_temp['tuvo_error'])
    
    # Le ponemos nombres mas bonitos a las columnas para que se entienda
    tabla_contingencia.columns = ['Sin Errores (Falso)', 'Con Errores (Verdadero)']
    
    if imprimir_mensajes:
        print("Tabla de Contingencia:")
        print(tabla_contingencia)
        print("\n")
        
    # Hacemos la prueba de Chi-Cuadrada
    try:
        resultado = stats.chi2_contingency(tabla_contingencia)
        estadistico = resultado.statistic
        p_valor = resultado.pvalue
    except ValueError as e:
        if imprimir_mensajes:
            print("[Prueba] Ocurrio un error en Chi-Cuadrada:", e)
        estadistico = 0
        p_valor = 1.0
        
    if imprimir_mensajes:
        print(f"-> Estadistico Chi-Cuadrado: {estadistico:.2f}")
        print(f"-> Valor-p (p-value): {p_valor:.4e}")
        
        if p_valor < 0.05:
            print("\nCONCLUSION: Rechazamos H0.")
            print("Sí hay evidencia estadisticamente significativa de que la inyeccion de falla (Round) afecta la aparicion de errores.")
        else:
            print("\nCONCLUSION: No podemos rechazar H0.")
            print("No se demostro que el round afecte si salen errores o no.")
            
    return {
        'estadistico_chi2': estadistico,
        'p_value': p_valor,
        'tabla': tabla_contingencia
    }


def modelo_regresion_lineal(df_modelo: pd.DataFrame, imprimir_mensajes: bool = True):
    # Regresion Lineal Multiple para intentar predecir el volumen de errores.
    if imprimir_mensajes:
        print("\n" + "="*50)
        print("MODELO DE REGRESION LINEAL MULTIPLE")
        print("="*50)
        
    # Filtramos para quedarnos solo con el round donde se inyecto la falla
    datos_r1 = df_modelo[df_modelo['round_id'] == 'round_1'].copy()
    
    # Preparamos las variables
    y = datos_r1['ERROR_TOTAL']
    
    # Creamos variables dummy para el subsistema (porque es texto)
    # drop_first=True evita el problema de colinealidad perfecta
    x_variables = pd.get_dummies(datos_r1[['WARNING', 'subsystem']], drop_first=True)
    
    # Importante: para statsmodels hay que agregarle la constante (interseccion con el eje Y) manual
    x_variables = sm.add_constant(x_variables)
    
    # Entrenamos el modelo usando Minimos Cuadrados Ordinarios (OLS)
    modelo = sm.OLS(y, x_variables.astype(float)).fit()
    
    if imprimir_mensajes:
        print(modelo.summary())
        print(f"-> R-cuadrado: {modelo.rsquared:.4f} (El modelo explica el {modelo.rsquared*100:.1f}% de la varianza en los errores).")
        print("-> Revisa los 'P>|t|' en la tabla de arriba. Si son menores a 0.05, esa variable influye significativamente en generar más errores.")
        
    return modelo


def evaluar_supuestos_y_metricas_regresion(modelo):
    print("EVALUACION DE SUPUESTOS Y METRICAS DEL MODELO")
    
    # Extraemos los residuos (la diferencia entre lo real y lo que predijo el modelo)
    residuos = modelo.resid
    variables_x = modelo.model.exog
    
    # 1. Normalidad de los residuos (Shapiro-Wilk)
    print("\n1. NORMALIDAD DE RESIDUOS (Prueba de Shapiro-Wilk)")
    stat_shapiro, p_shapiro = shapiro(residuos)
    print(f"   Valor-p: {p_shapiro:.4e}")
    if p_shapiro < 0.05:
        print("   Los residuos NO son normales.")
        print("   Los intervalos de confianza y los p-values del resumen (summary) podrian ser imprecisos.")
    else:
        print("   Los residuos se distribuyen normalmente.")
        
    # 2. Homocedasticidad (Breusch-Pagan)
    print("\n2. HOMOCEDASTICIDAD (Prueba de Breusch-Pagan)")
    # La prueba devuelve varios valores, nos interesa el p-value del multiplicador de Lagrange (indice 1)
    # o el p-value de la prueba f (indice 3). Usaremos el multiplicador de Lagrange.
    bp_test = het_breuschpagan(residuos, variables_x)
    p_bp = bp_test[1]
    print(f"   Valor-p: {p_bp:.4e}")
    if p_bp < 0.05:
        print("   Hay HETEROCEDASTICIDAD (la varianza del error no es constante).")
        print("   El modelo se equivoca de forma distinta dependiendo de cuan grandes sean los valores. Hace que las pruebas de significancia sean menos confiables.")
    else:
        print("   Hay homocedasticidad (la varianza del error es estable).")
        
    # 3. Multicolinealidad (VIF)
    print("\n3. MULTICOLINEALIDAD (Factor de Inflacion de Varianza - VIF)")
    nombres_variables = modelo.model.exog_names
    hay_multicolinealidad = False
    
    for i in range(1, variables_x.shape[1]): # Empezamos en 1 para saltarnos la constante (Intercepto)
        vif = variance_inflation_factor(variables_x, i)
        print(f"   - {nombres_variables[i]}: VIF = {vif:.2f}")
        if vif > 5:
            hay_multicolinealidad = True
            
    if hay_multicolinealidad:
        print("   VIF mayor a 5 detectado en alguna variable.")
        print("   Impacto: Algunas variables independientes estan muy correlacionadas entre si (hacen lo mismo). El modelo puede confundirse sobre cual variable es realmente la culpable de los errores.")
    else:
        print("   No hay multicolinealidad grave.")
        
    # 4. Metricas de Rendimiento Absoluto
    print("\n4. METRICAS DE RENDIMIENTO (ERROR)")
    mae = np.mean(np.abs(residuos))
    rmse = np.sqrt(np.mean(residuos**2))
    print(f"   - MAE (Error Absoluto Medio): {mae:.2f} errores")
    print(f"   - RMSE (Raiz del Error Cuadratico Medio): {rmse:.2f} errores")
    print("    En promedio, el modelo se equivoca por esta cantidad de errores al intentar predecir el impacto de una falla.")


def evaluar_normalidad_variables(df_modelo: pd.DataFrame, variables: list | None = None, imprimir_mensajes: bool = True) -> pd.DataFrame:
    """
    Evalúa la normalidad de las variables de telemetría continuas/conteo mediante la prueba de Shapiro-Wilk.
    """
    if variables is None:
        variables = ['ERROR_TOTAL', 'WARNING', 'total_log_lines']
    variables_existentes = [v for v in variables if v in df_modelo.columns]
    
    resultados = []
    for var in variables_existentes:
        datos_validos = df_modelo[var].dropna()
        if len(datos_validos) >= 3:
            stat, p_val = shapiro(datos_validos[:5000])
            es_normal = "Sí" if p_val >= 0.05 else "No (Sesgada)"
            resultados.append({
                "Variable": var,
                "Estadistico_Shapiro": stat,
                "p_value": p_val,
                "Es_Normal": es_normal
            })
            
    df_res = pd.DataFrame(resultados)
    
    if imprimir_mensajes:
        print("\n" + "="*50)
        print("EVALUACIÓN FORMAL DE NORMALIDAD (SHAPIRO-WILK DIRECTO)")
        print("="*50)
        print(df_res.to_string(index=False))
        
    return df_res


def estimar_bootstrap_ic(df_modelo: pd.DataFrame, columna: str = "ERROR_TOTAL", grupo_col: str = "round_id", n_bootstrap: int = 1000, ci: float = 95.0, imprimir_mensajes: bool = True) -> dict:
    """
    Estima los intervalos de confianza mediante Bootstrap (remuestreo con reemplazo)
    para la media y la mediana de una variable de telemetría segregada por grupo (p. ej. round_id).
    """
    if imprimir_mensajes:
        print("\n" + "="*50)
        print(f"ESTIMACIÓN CON BOOTSTRAP (IC {ci}%) - Variable: {columna}")
        print("="*50)
        
    np.random.seed(42)
    resultados = {}
    
    alpha_inf = (100.0 - ci) / 2.0
    alpha_sup = 100.0 - alpha_inf
    
    grupos = df_modelo[grupo_col].unique()
    for grupo in grupos:
        datos_grupo = df_modelo[df_modelo[grupo_col] == grupo][columna].dropna().values
        n = len(datos_grupo)
        
        if n == 0:
            continue
            
        medias_boot = np.empty(n_bootstrap)
        medianas_boot = np.empty(n_bootstrap)
        
        for i in range(n_bootstrap):
            muestra = np.random.choice(datos_grupo, size=n, replace=True)
            medias_boot[i] = np.mean(muestra)
            medianas_boot[i] = np.median(muestra)
            
        ic_media = (np.percentile(medias_boot, alpha_inf), np.percentile(medias_boot, alpha_sup))
        ic_mediana = (np.percentile(medianas_boot, alpha_inf), np.percentile(medianas_boot, alpha_sup))
        
        resultados[grupo] = {
            'media_obs': np.mean(datos_grupo),
            'ic_media': ic_media,
            'mediana_obs': np.median(datos_grupo),
            'ic_mediana': ic_mediana
        }
        
        if imprimir_mensajes:
            print(f"Grupo [{grupo}] (n={n}):")
            print(f"   - Media observada:   {np.mean(datos_grupo):.2f} (IC {ci}% Bootstrap: [{ic_media[0]:.2f}, {ic_media[1]:.2f}])")
            print(f"   - Mediana observada: {np.median(datos_grupo):.2f} (IC {ci}% Bootstrap: [{ic_mediana[0]:.2f}, {ic_mediana[1]:.2f}])")
            
    return resultados


def comparar_grupos_no_parametricos(df_modelo: pd.DataFrame, imprimir_mensajes: bool = True) -> dict:
    """
    Realiza pruebas de significancia no paramétricas sobre las variables de conteo:
    1. Mann-Whitney U (o Wilcoxon Rank-Sum) entre Round 1 vs Round 2.
    2. Kruskal-Wallis entre los subsistemas (Nova, Cinder, Neutron) en Round 1.
    """
    if imprimir_mensajes:
        print("\n" + "="*50)
        print("PRUEBAS NO PARAMÉTRICAS DE COMPARACIÓN DE GRUPOS")
        print("="*50)
        
    # 1. Mann-Whitney U: Round 1 vs Round 2 en ERROR_TOTAL
    r1_errors = df_modelo[df_modelo['round_id'] == 'round_1']['ERROR_TOTAL'].dropna()
    r2_errors = df_modelo[df_modelo['round_id'] == 'round_2']['ERROR_TOTAL'].dropna()
    
    stat_mw, p_mw = stats.mannwhitneyu(r1_errors, r2_errors, alternative='two-sided')
    
    if imprimir_mensajes:
        print("1. Mann-Whitney U (ERROR_TOTAL: Round 1 vs Round 2):")
        print(f"   - Estadistico U: {stat_mw:.2f}")
        print(f"   - Valor-p: {p_mw:.4e}")
        if p_mw < 0.05:
            print("   -> CONCLUSION: Diferencia estadisticamente significativa en la magnitud de errores entre rounds.")
        else:
            print("   -> CONCLUSION: No hay diferencia significativa en la magnitud de errores.")
            
    # 2. Kruskal-Wallis: ERROR_TOTAL por Subsistema en Round 1
    datos_r1 = df_modelo[df_modelo['round_id'] == 'round_1']
    subsistemas = datos_r1['subsystem'].unique()
    grupos_sub = [datos_r1[datos_r1['subsystem'] == sub]['ERROR_TOTAL'].dropna() for sub in subsistemas]
    
    stat_kw, p_kw = stats.kruskal(*grupos_sub)
    
    if imprimir_mensajes:
        print("\n2. Kruskal-Wallis (ERROR_TOTAL en Round 1 por Subsistema):")
        print(f"   - Estadistico H (Kruskal-Wallis): {stat_kw:.2f}")
        print(f"   - Valor-p: {p_kw:.4e}")
        if p_kw < 0.05:
            print("   -> CONCLUSION: Existen diferencias significativas en el volumen de errores entre los subsistemas.")
        else:
            print("   -> CONCLUSION: No se detectaron diferencias significativas en errores entre subsistemas.")
            
    return {
        'mann_whitney_u': {'statistic': stat_mw, 'p_value': p_mw},
        'kruskal_wallis': {'statistic': stat_kw, 'p_value': p_kw}
    }


def modelo_regresion_conteo(df_modelo: pd.DataFrame, tipo_modelo: str = "log_ols", imprimir_mensajes: bool = True):
    """
    Modelado alternativo para datos de conteo con sesgo:
    - tipo_modelo='log_ols': OLS transformando la variable dependiente a log(1 + ERROR_TOTAL).
    - tipo_modelo='poisson': Modelo Lineal Generalizado (GLM) con familia Poisson.
    """
    datos_r1 = df_modelo[df_modelo['round_id'] == 'round_1'].copy()
    
    if tipo_modelo == "log_ols":
        if imprimir_mensajes:
            print("\n" + "="*50)
            print("MODELO DE REGRESIÓN OLS TRANSFORMADO: log(1 + ERROR_TOTAL)")
            print("="*50)
            
        datos_r1['log_ERROR_TOTAL'] = np.log1p(datos_r1['ERROR_TOTAL'])
        y = datos_r1['log_ERROR_TOTAL']
        x_vars = pd.get_dummies(datos_r1[['WARNING', 'subsystem']], drop_first=True)
        x_vars = sm.add_constant(x_vars)
        
        modelo = sm.OLS(y, x_vars.astype(float)).fit()
        
        if imprimir_mensajes:
            print(modelo.summary())
            print(f"-> R-cuadrado (Log-OLS): {modelo.rsquared:.4f} (Explica el {modelo.rsquared*100:.1f}% de la varianza en log-errores).")
            
        return modelo
        
    elif tipo_modelo in ["poisson", "glm"]:
        if imprimir_mensajes:
            print("\n" + "="*50)
            print("MODELO DE REGRESIÓN DE POISSON (GLM CONTEO)")
            print("="*50)
            
        y = datos_r1['ERROR_TOTAL']
        x_vars = pd.get_dummies(datos_r1[['WARNING', 'subsystem']], drop_first=True)
        x_vars = sm.add_constant(x_vars)
        
        modelo = sm.GLM(y, x_vars.astype(float), family=sm.families.Poisson()).fit()
        
        if imprimir_mensajes:
            print(modelo.summary())
            
        return modelo
    else:
        raise ValueError("tipo_modelo debe ser 'log_ols' o 'poisson'")


def graficar_diagnostico_residuos(modelo, ruta_guardar: str | None = None):
    """
    Genera gráficos de diagnóstico para evaluar los residuos de un modelo de regresión:
    1. Gráfico Q-Q de residuos.
    2. Gráfico de Residuos vs. Valores Ajustados (Fitted).
    """
    import matplotlib.pyplot as plt
    residuos = modelo.resid
    valores_ajustados = modelo.fittedvalues
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # 1. Plot Q-Q
    sm.qqplot(residuos, line='s', ax=axes[0])
    axes[0].set_title("Gráfico Q-Q de Residuos", fontsize=12)
    
    # 2. Residuos vs Fitted
    axes[1].scatter(valores_ajustados, residuos, alpha=0.6, color='indigo')
    axes[1].axhline(0, color='red', linestyle='--')
    axes[1].set_title("Residuos vs. Valores Ajustados (Fitted)", fontsize=12)
    axes[1].set_xlabel("Valores Ajustados (Predicciones)", fontsize=10)
    axes[1].set_ylabel("Residuos", fontsize=10)
    
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()
    
