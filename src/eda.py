import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Configuracion global para que las graficas se vean bonitas
sns.set_theme(style="whitegrid", palette="muted")

def calcular_estadisticas_descriptivas(df: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    """
    Calcula medidas de tendencia central (media, mediana, moda) y dispersión
    (varianza, desviación estándar, rango, IQR, asimetría) para las variables numéricas de telemetría.
    """
    cols_num = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'TRACE', 'total_log_lines']
    cols_existentes = [c for c in cols_num if c in df.columns]
    
    stats_df = pd.DataFrame()
    stats_df['Media'] = df[cols_existentes].mean()
    stats_df['Mediana'] = df[cols_existentes].median()
    stats_df['Moda'] = df[cols_existentes].mode().iloc[0]
    stats_df['Varianza'] = df[cols_existentes].var()
    stats_df['Desv_Est'] = df[cols_existentes].std()
    stats_df['Min'] = df[cols_existentes].min()
    stats_df['Max'] = df[cols_existentes].max()
    stats_df['Rango'] = stats_df['Max'] - stats_df['Min']
    stats_df['IQR'] = df[cols_existentes].quantile(0.75) - df[cols_existentes].quantile(0.25)
    stats_df['Asimetria'] = df[cols_existentes].skew()
    
    if imprimir_mensajes:
        print("=" * 60)
        print("ESTADÍSTICA DESCRIPTIVA GLOBAL (VARIABLES NUMÉRICAS)")
        print("=" * 60)
        print(stats_df.to_string())
        
    return stats_df


def graficar_distribucion_fallas(df: pd.DataFrame, ruta_guardar: str | None = None):
    """
    Grafica cuantos tests fallaron en el round 1 por cada subsistema.
    """
    plt.figure(figsize=(8, 5))
    
    # Calculamos el porcentaje de fallas por subsistema
    tasa_falla = df.groupby('subsystem', observed=False)['round_1_failure'].mean() * 100
    tasa_falla = tasa_falla.sort_values(ascending=False)
    
    ax = sns.barplot(x=tasa_falla.index, y=tasa_falla.values, hue=tasa_falla.index, legend=False, palette="crest")
    
    plt.title("Tasa de Falla Inyectada (Round 1) por Subsistema", fontsize=14, pad=15)
    plt.ylabel("Porcentaje de Falla (%)", fontsize=12)
    plt.xlabel("Subsistema (Nova, Cinder, Neutron)", fontsize=12)
    
    # Le ponemos el numerito arriba a las barras para que quede mas claro
    for p in ax.patches:
        ax.annotate(f"{p.get_height():.1f}%", 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha='center', va='bottom', fontsize=11, color='black', xytext=(0, 5), 
                    textcoords='offset points')
    
    plt.ylim(0, max(tasa_falla.values) + 15)
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()


def graficar_logs_por_nivel(df_logs: pd.DataFrame, ruta_guardar: str | None = None):
    """
    Grafica la cantidad de logs segun su nivel de severidad (INFO, DEBUG, ERROR, etc).
    """
    plt.figure(figsize=(8, 5))
    
    # Contamos cuantas lineas hay de cada nivel
    conteo_niveles = df_logs['level'].value_counts().reset_index()
    conteo_niveles.columns = ['Nivel', 'Cantidad']
    
    # Filtramos para quitar los que casi no salen y que la grafica no se vea fea
    conteo_niveles = conteo_niveles[conteo_niveles['Cantidad'] > 0]
    
    sns.barplot(data=conteo_niveles, x='Nivel', y='Cantidad', hue='Nivel', legend=False, palette="viridis")
    
    plt.title("Volumen Total de Logs por Nivel de Severidad", fontsize=14, pad=15)
    plt.ylabel("Cantidad de Lineas (escala logaritmica)", fontsize=12)
    plt.xlabel("Nivel del Log", fontsize=12)
    plt.yscale("log")
    
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()


def graficar_mapa_calor_fallas(df: pd.DataFrame, ruta_guardar: str | None = None):
    plt.figure(figsize=(10, 6))
    
    # Hacemos una tabla dinamica cruzando subsistema vs origen de la falla
    tabla_cruzada = pd.crosstab(df['fault_origin'], df['subsystem'], normalize='columns') * 100
    
    # Si esta vacia no graficamos para que no truene
    if tabla_cruzada.empty:
        print("No hay datos suficientes para el mapa de calor.")
        return
        
    sns.heatmap(tabla_cruzada, annot=True, fmt=".1f", cmap="YlOrRd", cbar_kws={'label': '% de frecuencia relativa'})
    
    plt.title("Mapa de Calor: Origen de la Falla vs Subsistema Afectado", fontsize=14, pad=15)
    plt.ylabel("Origen de la Falla (fault_origin)", fontsize=12)
    plt.xlabel("Subsistema", fontsize=12)
    
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()


def graficar_comparacion_rounds(df_logs: pd.DataFrame, ruta_guardar: str | None = None):
    plt.figure(figsize=(9, 5))
    
    # Solo nos interesan los logs feos (WARNING, ERROR, CRITICAL)
    logs_feos = df_logs[df_logs['level'].isin(['WARNING', 'ERROR', 'CRITICAL'])].copy()
    
    if logs_feos.empty:
        print("No encontramos logs de error o warning para comparar.")
        return
        
    # Limpiamos las categorias que no se usaron para que no salgan vacias en la grafica
    logs_feos['level'] = logs_feos['level'].cat.remove_unused_categories()
    
    sns.countplot(data=logs_feos, x='round_id', hue='level', palette="Reds")
    
    plt.title("Comparacion de Logs de Error/Warning: Round 1 (con falla) vs Round 2 (Control)", fontsize=14, pad=15)
    plt.ylabel("Cantidad de Logs", fontsize=12)
    plt.xlabel("Round del Experimento", fontsize=12)
    
    plt.legend(title="Nivel del Log")
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()


def graficar_matriz_correlacion(df: pd.DataFrame, metodo: str = "spearman", ruta_guardar: str | None = None):
    """
    Calcula y grafica la matriz de correlación (Spearman o Pearson) entre conteos de log y fallas.
    """
    plt.figure(figsize=(9, 7))
    
    cols_num = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'total_log_lines', 'round_1_failure', 'round_2_failure']
    cols_existentes = [c for c in cols_num if c in df.columns]
    
    df_corr = df[cols_existentes].copy()
    for col in cols_existentes:
        df_corr[col] = df_corr[col].astype(float)
        
    corr_matrix = df_corr.corr(method=metodo)
    
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
    
    plt.title(f"Matriz de Correlación de {metodo.capitalize()} (Variables de Log y Fallas)", fontsize=14, pad=15)
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()
        
    return corr_matrix


def graficar_boxplots_outliers(df: pd.DataFrame, columna: str = "total_log_lines", ruta_guardar: str | None = None):
    """
    Genera boxplots para identificar outliers por subsistema y resultado de la falla.
    """
    plt.figure(figsize=(10, 6))
    
    sns.boxplot(data=df, x='subsystem', y=columna, hue='round_1_failure', palette="Set2")
    plt.yscale("log")
    
    plt.title(f"Boxplot de Deteccion de Outliers: {columna} por Subsistema y Falla", fontsize=14, pad=15)
    plt.ylabel(f"{columna} (escala logarítmica)", fontsize=12)
    plt.xlabel("Subsistema", fontsize=12)
    
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()


def graficar_histograma_kde(df: pd.DataFrame, columna: str = "total_log_lines", ruta_guardar: str | None = None):
    """
    Genera histograma con curva de densidad KDE para evaluar la forma de la distribución.
    """
    plt.figure(figsize=(10, 5))
    
    sns.histplot(df[columna], kde=True, bins=30, color="teal")
    
    plt.title(f"Histograma y Estimacion de Densidad (KDE) de {columna}", fontsize=14, pad=15)
    plt.xlabel(columna, fontsize=12)
    plt.ylabel("Frecuencia", fontsize=12)
    
    plt.tight_layout()
    if ruta_guardar:
        plt.savefig(ruta_guardar, dpi=150)
        plt.close()
    else:
        plt.show()
