import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuracion global para que las graficas se vean bonitas
sns.set_theme(style="whitegrid", palette="muted")

def graficar_distribucion_fallas(df: pd.DataFrame):
    """
    Grafica cuantos tests fallaron en el round 1 por cada subsistema.
    """
    plt.figure(figsize=(8, 5))
    
    # Calculamos el porcentaje de fallas por subsistema
    tasa_falla = df.groupby('subsystem')['round_1_failure'].mean() * 100
    tasa_falla = tasa_falla.sort_values(ascending=False)
    
    ax = sns.barplot(x=tasa_falla.index, y=tasa_falla.values, hue=tasa_falla.index, legend=False)
    
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
    plt.show()


def graficar_logs_por_nivel(df_logs: pd.DataFrame):
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
    
    # Ponemos la escala en logaritmo porque hay muchisimos mas DEBUG que ERROR
    plt.yscale("log")
    
    plt.tight_layout()
    plt.show()


def graficar_mapa_calor_fallas(df: pd.DataFrame):
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
    plt.show()


def graficar_comparacion_rounds(df_logs: pd.DataFrame):
    plt.figure(figsize=(9, 5))
    
    # Solo nos interesan los logs feos (WARNING, ERROR, CRITICAL)
    logs_feos = df_logs[df_logs['level'].isin(['WARNING', 'ERROR', 'CRITICAL'])].copy()
    
    if logs_feos.empty:
        print("Mmm, no encontramos logs de error o warning para comparar.")
        return
        
    # Limpiamos las categorias que no se usaron para que no salgan vacias en la grafica
    logs_feos['level'] = logs_feos['level'].cat.remove_unused_categories()
    
    sns.countplot(data=logs_feos, x='round_id', hue='level', palette="Reds")
    
    plt.title("Comparacion de Logs de Error/Warning: Round 1 (con falla) vs Round 2 (Control)", fontsize=14, pad=15)
    plt.ylabel("Cantidad de Logs", fontsize=12)
    plt.xlabel("Round del Experimento", fontsize=12)
    
    plt.legend(title="Nivel del Log")
    plt.tight_layout()
    plt.show()
