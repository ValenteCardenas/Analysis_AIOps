from pathlib import Path
import re
import pandas as pd

# Directorio por defecto de los datos (busca en la raiz o en data/)
_raiz = Path(__file__).resolve().parent.parent
_opciones_datos = [
    _raiz / "Fault-Injection-Dataset-master",
    _raiz / "data" / "Fault-Injection-Dataset",
    _raiz / "data" / "Fault-Injection-Dataset-master",
    _raiz / "data",
]
CARPETA_DATOS = next((p for p in _opciones_datos if p.is_dir()), _opciones_datos[0])

SISTEMAS = ("Nova", "Cinder", "Neutron")

# Regex para leer las lineas del log, me costo un poco armarlo jaja
PATRON_LOG = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})"  # Fecha y hora
    r"\s+(\d+)"                                          # Proceso (PID)
    r"\s+(\w+)"                                          # Nivel del log (INFO, DEBUG, etc)
    r"\s+([\w.]+)"                                       # Modulo
    r"\s+(\[.*?\])"                                      # ID del request
    r"\s+(.+)$"                                          # Mensaje principal
)

def leer_linea_log(linea: str) -> dict | None:
    # Esta funcion saca los datos de una sola linea de log
    match = PATRON_LOG.match(linea.strip())
    if match:
        diccionario_log = {
            "timestamp": match.group(1),
            "pid": int(match.group(2)),
            "level": match.group(3),
            "module": match.group(4),
            "request_id": match.group(5).strip("[]"),
            "message": match.group(6),
        }
        return diccionario_log
    else:
        return None

def procesar_archivo_log(ruta_log: Path) -> pd.DataFrame:
    # Metemos todas las lineas parseadas en una lista
    lineas_buenas = []
    try:
        # A veces el texto viene con caracteres raros, por eso el errors="ignore"
        texto_completo = ruta_log.read_text(encoding="utf-8", errors="ignore")
    except Exception as error_lectura:
        # Si falla regresamos un df vacio para que no truene el programa
        print("Error leyendo archivo:", error_lectura)
        return pd.DataFrame()

    # Recorremos cada linea del archivo
    for linea in texto_completo.splitlines():
        linea_parseada = leer_linea_log(linea)
        if linea_parseada != None:
            lineas_buenas.append(linea_parseada)

    df_final = pd.DataFrame(lineas_buenas)
    return df_final

def armar_tabla_logs(
    carpeta_dataset: Path | None = None,
    *,
    limite_pruebas: int | None = None,
    rondas: tuple[str, ...] = ("round_1", "round_2"),
    imprimir_mensajes: bool = True,
) -> pd.DataFrame:
    
    # Si no nos pasan carpeta, usamos la por defecto
    if carpeta_dataset == None:
        carpeta_dataset = CARPETA_DATOS
    else:
        carpeta_dataset = Path(carpeta_dataset)
        
    lista_de_dataframes = []

    for sistema in SISTEMAS:
        carpeta_sistema = carpeta_dataset / sistema
        # Comprobamos que exista la carpeta
        if not carpeta_sistema.is_dir():
            continue

        # Sacamos todas las carpetas que empiezan con Test_
        carpetas_pruebas = []
        for carpeta in carpeta_sistema.iterdir():
            if carpeta.is_dir() and carpeta.name.startswith("Test_"):
                carpetas_pruebas.append(carpeta)
        carpetas_pruebas.sort() # Ordenamos para que se vea bonito

        if limite_pruebas != None:
            carpetas_pruebas = carpetas_pruebas[:limite_pruebas]

        if imprimir_mensajes:
            print(f"[ETL-Logs] Procesando {sistema} que tiene {len(carpetas_pruebas)} pruebas")

        # Vamos a iterar sobre cada prueba
        for indice, prueba_dir in enumerate(carpetas_pruebas):
            id_prueba = prueba_dir.name
            logs_dir = prueba_dir / "logs"
            if not logs_dir.is_dir():
                continue

            for ronda in rondas:
                ronda_dir = logs_dir / ronda
                if not ronda_dir.is_dir():
                    continue

                # Recorrer subdirectorios de componentes como nova, cinder, neutron, etc.
                for componente_dir in ronda_dir.iterdir():
                    if not componente_dir.is_dir():
                        continue
                    if componente_dir.name == "foreground_wl":
                        # Saltamos esto porque los logs del workload se procesan aparte
                        continue

                    # Buscamos todos los logs bzip2 extraidos
                    for archivo_log in componente_dir.glob("*.log.bzip2.out"):
                        df_log_individual = procesar_archivo_log(archivo_log)
                        if df_log_individual.empty:
                            continue

                        # Le agregamos columnas para saber de donde salio
                        df_log_individual["subsystem"] = sistema
                        df_log_individual["test_id"] = id_prueba
                        df_log_individual["round_id"] = ronda
                        df_log_individual["log_source"] = componente_dir.name
                        df_log_individual["log_file_name"] = archivo_log.name
                        
                        lista_de_dataframes.append(df_log_individual)

            if imprimir_mensajes and (indice + 1) % 50 == 0:
                print(f"   Ya procesamos {indice + 1} de {len(carpetas_pruebas)} pruebas de {sistema}...")

    # Juntamos todo en un solo DataFrame
    if len(lista_de_dataframes) == 0:
        if imprimir_mensajes:
            print("[ETL-Logs] No encontramos nada util para parsear.")
        return pd.DataFrame()

    df_resultado = pd.concat(lista_de_dataframes, ignore_index=True)

    # Transformamos el texto del timestamp a un objeto de fecha de pandas
    df_resultado["timestamp"] = pd.to_datetime(
        df_resultado["timestamp"], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce"
    )

    if imprimir_mensajes:
        print(
            f"[ETL-Logs] Se estrucuturaron {len(df_resultado):,} lineas "
            f"de {df_resultado['test_id'].nunique()} pruebas diferentes."
        )

    return df_resultado


def cargar_csvs_fallas(carpeta_dataset: Path | None = None) -> pd.DataFrame:
    if carpeta_dataset == None:
        carpeta_dataset = CARPETA_DATOS
    else:
        carpeta_dataset = Path(carpeta_dataset)

    tablas = []
    for sistema in SISTEMAS:
        ruta_csv = carpeta_dataset / f"{sistema.lower()}.csv"
        es_tsv = False
        if not ruta_csv.exists():
            ruta_csv = carpeta_dataset / f"{sistema.lower()}.tsv"
            es_tsv = True

        if not ruta_csv.exists():
            continue

        try:
            if es_tsv:
                tabla_sistema = pd.read_csv(ruta_csv, sep="\t")
            else:
                tabla_sistema = pd.read_csv(ruta_csv)
                if len(tabla_sistema.columns) <= 1:
                    tabla_sistema = pd.read_csv(ruta_csv, sep="\t")
        except Exception:
            tabla_sistema = pd.read_csv(ruta_csv, sep="\t")

        # Le cambiamos los nombres a las columnas para que queden mejor
        nuevas_columnas = []
        for col in tabla_sistema.columns:
            nombre_limpio = col.strip().lower().replace(" ", "_")
            nuevas_columnas.append(nombre_limpio)
        tabla_sistema.columns = nuevas_columnas

        tabla_sistema = tabla_sistema.rename(columns={
            "test": "test_id",
            "round_1": "round_1_failure",
            "round_2": "round_2_failure",
        })
        tabla_sistema["subsystem"] = sistema
        cols_keep = [c for c in ["test_id", "round_1_failure", "round_2_failure", "subsystem"] if c in tabla_sistema.columns]
        tabla_sistema = tabla_sistema[cols_keep]
        tablas.append(tabla_sistema)

    if not tablas:
        return pd.DataFrame()

    resultado_final = pd.concat(tablas, ignore_index=True)

    # Cambiamos los strings de yes/no o failure/no_failure a valores de verdad o falso
    mapeo_booleanos = {
        "yes": True, "no": False,
        "failure": True, "no_failure": False,
        "true": True, "false": False,
    }
    for columna in ("round_1_failure", "round_2_failure"):
        if columna in resultado_final.columns:
            s_map = resultado_final[columna].astype(str).str.strip().str.lower().map(mapeo_booleanos)
            if s_map.notna().any():
                resultado_final[columna] = s_map.fillna(resultado_final[columna]).astype(bool)

    return resultado_final



#Aqui se sacan los metadatos de las fallas
def _leer_info_fip(ruta_fip: Path) -> dict:
    # Abre y lee el archivo de fip_info y lo hace un diccionario
    informacion_fip = {}
    if not ruta_fip.exists():
        return informacion_fip

    texto = ruta_fip.read_text(encoding="utf-8", errors="replace")
    for linea in texto.strip().splitlines():
        if ":" in linea:
            # partimos la linea donde esta los dos puntos
            llave, dos_puntos, valor = linea.partition(":")
            llave = llave.strip().lower().replace(" ", "_")
            informacion_fip[llave] = valor.strip()
            
    return informacion_fip

def cargar_metadatos_fallas(carpeta_dataset: Path | None = None) -> pd.DataFrame:
    if carpeta_dataset == None:
        carpeta_dataset = CARPETA_DATOS
    else:
        carpeta_dataset = Path(carpeta_dataset)

    registros = []
    for sistema in SISTEMAS:
        carpeta_sistema = carpeta_dataset / sistema
        if not carpeta_sistema.is_dir():
            continue

        # Iteramos por todas las carpetas de pruebas
        lista_carpetas = list(carpeta_sistema.iterdir())
        lista_carpetas.sort()
        
        for prueba_dir in lista_carpetas:
            if not prueba_dir.is_dir() or not prueba_dir.name.startswith("Test_"):
                continue

            ruta_fip = prueba_dir / "fip_info.data"
            info = _leer_info_fip(ruta_fip)
            info["test_id"] = prueba_dir.name
            info["subsystem"] = sistema
            registros.append(info)

    df_metadatos = pd.DataFrame(registros)
    return df_metadatos


def _leer_log_error_workload(ruta_log_error: Path) -> dict:
    resultado = {"assertion_result": None, "error_raw": None}
    if not ruta_log_error.exists():
        return resultado

    texto_log = ruta_log_error.read_text(encoding="utf-8", errors="replace").strip()
    
    if texto_log == "":
        resultado["error_raw"] = None
    else:
        resultado["error_raw"] = texto_log

    # Buscamos a ver si dice Assertion results
    busqueda = re.search(r"Assertion results?:\s*(.+)", texto_log, re.IGNORECASE)
    if busqueda:
        resultado["assertion_result"] = busqueda.group(1).strip()

    return resultado

def _leer_log_disparo(ruta_trigger: Path) -> dict:
    resultado = {"trigger_timestamp": None}
    if not ruta_trigger.exists():
        return resultado

    texto_trigger = ruta_trigger.read_text(encoding="utf-8", errors="replace").strip()
    # Aca el profe puso que el formato es asi: "2018-06-26 03:28:34.195098 [manager.pyc]: Injection activated!"
    match_regex = re.match(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)", texto_trigger)
    if match_regex:
        resultado["trigger_timestamp"] = match_regex.group(1)

    return resultado


def _contar_niveles_log(directorio_log: Path) -> dict[str, int]:
    conteo_niveles = {
        "DEBUG": 0, "INFO": 0, "WARNING": 0,
        "ERROR": 0, "CRITICAL": 0, "TRACE": 0,
    }
    lineas_totales = 0

    if not directorio_log.is_dir():
        conteo_niveles["total_log_lines"] = 0
        return conteo_niveles

    for sub_carpeta in directorio_log.iterdir():
        if not sub_carpeta.is_dir() or sub_carpeta.name == "foreground_wl":
            continue
            
        for archivo_log in sub_carpeta.glob("*.log.bzip2.out"):
            try:
                texto_archivo = archivo_log.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
                
            for linea in texto_archivo.splitlines():
                lineas_totales = lineas_totales + 1
                datos_linea = leer_linea_log(linea)
                if datos_linea != None:
                    nivel = datos_linea["level"]
                    if nivel in conteo_niveles:
                        conteo_niveles[nivel] = conteo_niveles[nivel] + 1

    conteo_niveles["total_log_lines"] = lineas_totales
    return conteo_niveles

def crear_tabla_analisis(
    carpeta_dataset: Path | None = None,
    *,
    contar_logs: bool = True,
    imprimir_mensajes: bool = True,
) -> pd.DataFrame:

    if carpeta_dataset == None:
        carpeta_dataset = CARPETA_DATOS
    else:
        carpeta_dataset = Path(carpeta_dataset)

    if imprimir_mensajes:
        print("[ETL] Primero vamos a cargar los CSVs de fallas...")
    tabla_fallas = cargar_csvs_fallas(carpeta_dataset)

    if imprimir_mensajes:
        print("[ETL] Ahora cargamos los metadatos de las inyecciones...")
    tabla_metadatos = cargar_metadatos_fallas(carpeta_dataset)

    # Hacemos un join de las fallas y los metadatos
    tabla_maestra = tabla_fallas.merge(tabla_metadatos, on=["test_id", "subsystem"], how="left")

    # Vamos a ir recorriendo cada prueba para agregarle los demas logs
    lista_registros_extra = []
    cantidad_total = len(tabla_maestra)
    
    for indice, fila in tabla_maestra.iterrows():
        id_prueba = fila["test_id"]
        sistema = fila["subsystem"]
        carpeta_prueba = carpeta_dataset / sistema / id_prueba
        carpeta_ronda1 = carpeta_prueba / "logs" / "round_1"

        diccionario_registro = {}

        # Sacamos el error del workload
        carpeta_wl = carpeta_ronda1 / "foreground_wl"
        if carpeta_wl.is_dir():
            archivos_err = list(carpeta_wl.glob("*.err.log.bzip2.out"))
            if len(archivos_err) > 0:
                # Tomamos el primero que encuentre
                diccionario_registro.update(_leer_log_error_workload(archivos_err[0]))

        # Sacamos el trigger log
        ruta_trigger = carpeta_ronda1 / "trigger_log"
        diccionario_registro.update(_leer_log_disparo(ruta_trigger))

        # Y por ultimo contamos los logs si nos lo pidieron
        if contar_logs == True:
            diccionario_registro.update(_contar_niveles_log(carpeta_ronda1))

        lista_registros_extra.append(diccionario_registro)

        if imprimir_mensajes:
            if (indice + 1) % 100 == 0:
                print(f"   Llevamos procesadas {indice + 1} de {cantidad_total} pruebas...")

    tabla_extra = pd.DataFrame(lista_registros_extra)
    # Pegamos las dos tablas a lo largo de las columnas
    tabla_maestra = pd.concat([tabla_maestra.reset_index(drop=True), tabla_extra], axis=1)

    if imprimir_mensajes:
        print(f"ETL La tabla final tiene {len(tabla_maestra)} filas y {len(tabla_maestra.columns)} columnas.")

    return tabla_maestra


# SECCION DE LIMPIEZA: Funciones para limpiar y preparar los datos

def limpiar_valores_nulos(df: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    # Hacemos una copia para no echar a perder el original
    df_limpio = df.copy()

    nulos_antes = df_limpio.isnull().sum().sum()

    # Si assertion_result esta vacio, significa que la prueba no detecto ninguna falla
    df_limpio["assertion_result"] = df_limpio["assertion_result"].fillna("SIN_FALLA_DETECTADA")

    # Si no hay error crudo, le ponemos que no hubo error
    df_limpio["error_raw"] = df_limpio["error_raw"].fillna("sin_error")

    # Arreglamos la fecha y hora. Los nulos se quedan como NaT automaticamente
    df_limpio["trigger_timestamp"] = pd.to_datetime(
        df_limpio["trigger_timestamp"], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce"
    )

    nulos_despues = df_limpio.isnull().sum().sum()

    if imprimir_mensajes:
        print(f"[Limpieza] Teniamos {nulos_antes} nulos y ahora tenemos {nulos_despues}")
        print(f"           (El trigger_timestamp tiene {df_limpio['trigger_timestamp'].isna().sum()} nulos, esta bien)")

    return df_limpio


def quitar_duplicados(df: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    df_limpio = df.copy()
    # Checamos si hay filas repetidas
    duplicados = df_limpio.duplicated().sum()

    if duplicados > 0:
        # Si hay, las borramos
        df_limpio = df_limpio.drop_duplicates()
        if imprimir_mensajes:
            print(f"[Limpieza] Borramos {duplicados} filas repetidas.")
    else:
        if imprimir_mensajes:
            print("[Limpieza] Que bien, no hay filas repetidas.")

    return df_limpio


def arreglar_tipos_datos(df: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    df_limpio = df.copy()

    # Ponemos estas como categorias para que pandas no gaste tanta memoria
    columnas_categoricas = ["subsystem", "fault_type", "assertion_result"]
    for col in columnas_categoricas:
        if col in df_limpio.columns:
            df_limpio[col] = df_limpio[col].astype("category")

    # Por si acaso aseguramos que el timestamp sea fecha
    if df_limpio["trigger_timestamp"].dtype == "object" or df_limpio["trigger_timestamp"].dtype == "str":
        df_limpio["trigger_timestamp"] = pd.to_datetime(
            df_limpio["trigger_timestamp"], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce"
        )

    if imprimir_mensajes:
        print("[Limpieza] Ya arreglamos los tipos de datos:")
        print(f"           subsystem ahora es categoria ({df_limpio['subsystem'].cat.categories.tolist()})")
        print(f"           fault_type ahora es categoria ({df_limpio['fault_type'].nunique()} tipos diferentes)")
        print(f"           assertion_result ahora es categoria ({df_limpio['assertion_result'].nunique()} tipos)")
        print(f"           trigger_timestamp es {df_limpio['trigger_timestamp'].dtype}")

    return df_limpio


def simplificar_tipo_falla(df: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    df_limpio = df.copy()

    # Rompemos el tipo de falla a la mitad usando el guion medio
    # Ejemplo: OPENSTACK_MISSING_FUNCTION_CALL-VOLUME se hace dos partes
    partes = df_limpio["fault_type"].astype(str).str.rsplit("-", n=1, expand=True)
    df_limpio["fault_target"] = partes[1] if 1 in partes.columns else "UNKNOWN"

    # La primera parte la agarramos para sacar el origen
    prefijo = partes[0]

    # Origenes que ya conocemos
    origenes_conocidos = ["OPENSTACK", "DISKIO", "NETIO", "URLLIB", "URLPARSE", "OS"]
    
    lista_origenes = []
    lista_categorias = []
    for valor in prefijo:
        origen_encontrado = "OTRO"
        categoria = valor
        for origen in origenes_conocidos:
            if valor.startswith(origen + "_"):
                origen_encontrado = origen
                # Le mochamos el origen para quedarnos nomas con la categoria
                categoria = valor[len(origen) + 1:]
                break
        lista_origenes.append(origen_encontrado)
        lista_categorias.append(categoria)

    # Las guardamos en el df como categorias
    df_limpio["fault_origin"] = pd.Categorical(lista_origenes)
    df_limpio["fault_category"] = pd.Categorical(lista_categorias)
    df_limpio["fault_target"] = df_limpio["fault_target"].astype("category")

    if imprimir_mensajes:
        print("[Limpieza] Dividimos el tipo de falla en varias columnas:")
        print(f"           fault_origin -> {df_limpio['fault_origin'].nunique()} valores: {df_limpio['fault_origin'].value_counts().index.tolist()}")
        print(f"           fault_category -> {df_limpio['fault_category'].nunique()} categorias")
        print(f"           fault_target -> {df_limpio['fault_target'].nunique()} valores: {df_limpio['fault_target'].value_counts().index.tolist()}")

    return df_limpio


def limpiar_df_completo(df: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    if imprimir_mensajes:
        print("=" * 50)
        print("VAMOS A LIMPIAR LA TABLA PRINCIPAL")
        print("=" * 50)

    # Llamamos a todas las funciones una tras otra
    df = quitar_duplicados(df, imprimir_mensajes)
    df = limpiar_valores_nulos(df, imprimir_mensajes)
    df = arreglar_tipos_datos(df, imprimir_mensajes)
    df = simplificar_tipo_falla(df, imprimir_mensajes)

    if imprimir_mensajes:
        print(f"\n[Limpieza] Todo listo. Nos quedo una tabla de {df.shape[0]} filas y {df.shape[1]} columnas")
        print("=" * 50)

    return df


def limpiar_logs(df_logs: pd.DataFrame, imprimir_mensajes: bool = True) -> pd.DataFrame:
    df_limpio = df_logs.copy()
    filas_antes = len(df_limpio)

    # Quitamos los logs repetidos para no inflar los datos
    df_limpio = df_limpio.drop_duplicates(
        subset=["timestamp", "pid", "level", "module", "message", "test_id", "round_id"],
        keep="first"
    )
    duplicados_quitados = filas_antes - len(df_limpio)

    # Ponemos estas columnas como categoria para ahorrar espacio
    for col in ["level", "subsystem", "round_id", "log_source"]:
        df_limpio[col] = df_limpio[col].astype("category")

    # Acomodamos todo por fecha y hora para que el analisis quede bien
    df_limpio = df_limpio.sort_values("timestamp").reset_index(drop=True)

    if imprimir_mensajes:
        print(f"[Limpieza Logs] Quitamos {duplicados_quitados:,} lineas repetidas")
        print(f"[Limpieza Logs] Al final quedaron {len(df_limpio):,} lineas de log")
        print(f"[Limpieza Logs] Se acomodaron los tipos de datos y se ordeno todo por fecha")

    return df_limpio
