from pathlib import Path
import re
import pandas as pd

# Directorio por defecto de los datos
CARPETA_DATOS = Path(__file__).resolve().parent.parent / "Fault-Injection-Dataset-master"

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

# ---------------------------------------------------------------------------
# 1. Cargar los CSVs donde vienen los resultados de las fallas
# ---------------------------------------------------------------------------
def cargar_csvs_fallas(carpeta_dataset: Path | None = None) -> pd.DataFrame:
    if carpeta_dataset == None:
        carpeta_dataset = CARPETA_DATOS
    else:
        carpeta_dataset = Path(carpeta_dataset)

    tablas = []
    for sistema in SISTEMAS:
        ruta_csv = carpeta_dataset / f"{sistema.lower()}.csv"
        if not ruta_csv.exists():
            continue

        tabla_sistema = pd.read_csv(ruta_csv)
        
        # Le cambiamos los nombres a las columnas para que queden mejor
        nuevas_columnas = []
        for col in tabla_sistema.columns:
            nombre_limpio = col.strip().lower().replace(" ", "_")
            nuevas_columnas.append(nombre_limpio)
        tabla_sistema.columns = nuevas_columnas
        
        tabla_sistema = tabla_sistema.rename(columns={
            "test": "test_id",
            "round_1_failure": "round_1_failure",
            "round_2_failure": "round_2_failure",
        })
        tabla_sistema["subsystem"] = sistema
        tablas.append(tabla_sistema)

    resultado_final = pd.concat(tablas, ignore_index=True)

    # Cambiamos los strings de yes/no a valores de verdad o falso
    for columna in ("round_1_failure", "round_2_failure"):
        resultado_final[columna] = resultado_final[columna].str.strip().str.lower().map({"yes": True, "no": False})

    return resultado_final

# ---------------------------------------------------------------------------
# 2. Sacar los datos del archivo de inyeccion (fip_info.data)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 3. Sacar el log de error de la carga de trabajo
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 4. Encontrar a que hora exactamente se activo la falla (trigger log)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 5. Contar cuantas lineas hay de cada tipo de error
# ---------------------------------------------------------------------------
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

# ===========================================================================
# SECCION PRINCIPAL: Unimos todo en una super tabla
# ===========================================================================
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

