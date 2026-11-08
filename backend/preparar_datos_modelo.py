
import os
import pandas as pd

from dotenv import load_dotenv
from sqlalchemy import create_engine, URL

# =====================================================
# 1. CONFIGURACIÓN DE CONEXIÓN
# =====================================================

load_dotenv()

conexion = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    database=os.getenv("DB_NAME")
)

engine = create_engine(conexion)


# =====================================================
# 2. CONSULTAR Y CARGAR LAS TABLAS
# =====================================================

def cargar_tablas():

    consultas = {
        "materiales": """
            SELECT * FROM materiales
        """,

        "inventarios": """
            SELECT * FROM inventarios
        """,

        "demanda_historica": """
            SELECT * FROM demanda_historica
        """,

        "demanda_pronosticada": """
            SELECT * FROM demanda_pronosticada
        """,

        "proveedores": """
            SELECT * FROM proveedores_material
        """,

        "servicio": """
            SELECT * FROM parametros_servicio
        """,

        "restricciones": """
            SELECT * FROM restricciones_financieras
        """,

        "bodegas": """
            SELECT * FROM bodegas
        """,

        "zonas": """
            SELECT * FROM zonas_almacenamiento
        """,

        "costos_transferencia": """
            SELECT * FROM costos_transferencia
        """,

        "distribucion": """
            SELECT
                i.cod_material,
                i.id_zona,
                i.cantidad_existente,
                i.cantidad_comprometida,
                z.id_bodega,
                z.tipo_zona,
                b.nombre AS nombre_bodega
            FROM inventario_por_zona i
            INNER JOIN zonas_almacenamiento z
                ON i.id_zona = z.id_zona
            INNER JOIN bodegas b
                ON z.id_bodega = b.id_bodega
            WHERE i.id_escenario = 1
              AND i.tipo_registro = 'SIMULACION'
        """
    }

    datos = {}

    for nombre, consulta in consultas.items():
        datos[nombre] = pd.read_sql(
            consulta,
            engine
        )

    return datos


# =====================================================
# 3. VALIDAR INFORMACIÓN
# =====================================================

def validar_datos(datos):

    errores = []

    if datos["materiales"].empty:
        errores.append("No hay materiales registrados.")

    if datos["inventarios"].empty:
        errores.append("No hay inventarios registrados.")

    if datos["demanda_pronosticada"].empty:
        errores.append("No hay demanda pronosticada.")

    if datos["proveedores"].empty:
        errores.append("No hay proveedores registrados.")

    if datos["zonas"].empty:
        errores.append("No hay zonas de almacenamiento.")

    if datos["distribucion"].empty:
        errores.append("No existe distribución simulada.")

    # Comprobar que los materiales coincidan
    codigos_materiales = set(
        datos["materiales"]["cod_material"]
    )

    codigos_inventario = set(
        datos["inventarios"]["cod_material"]
    )

    if not codigos_inventario.issubset(codigos_materiales):
        errores.append(
            "Hay inventarios asociados a materiales inexistentes."
        )

    # Comprobar distribución
    if not datos["distribucion"].empty:

        codigos_distribucion = set(
            datos["distribucion"]["cod_material"]
        )

        if not codigos_distribucion.issubset(codigos_materiales):
            errores.append(
                "La distribución contiene materiales inexistentes."
            )

    return errores


# =====================================================
# 4. PREPARAR DATOS PARA EL MODELO
# =====================================================

def preparar_parametros(datos):

    materiales = datos["materiales"].copy()

    inventarios = datos["inventarios"].copy()

    demanda = datos["demanda_pronosticada"].copy()

    proveedores = datos["proveedores"].copy()

    zonas = datos["zonas"].copy()

    # Normalizar nombres de zonas
    materiales["zona_almacen"] = (
        materiales["zona_almacen"]
        .replace({"PATIO": "PATIO_ABIERTO"})
    )

    # Convertir periodo a fecha
    demanda["periodo"] = pd.to_datetime(
        demanda["periodo"] + "-01",
        format="%Y-%m-%d"
    )

    # Organizar demanda por material y periodo
    demanda = demanda.sort_values(
        ["cod_material", "periodo"]
    )

    # Unir inventarios con información de materiales
    datos_materiales = materiales.merge(
        inventarios,
        on="cod_material",
        how="left"
    )

    # Unir proveedores
    datos_materiales = datos_materiales.merge(
        proveedores,
        on="cod_material",
        how="left",
        suffixes=("", "_proveedor")
    )

    # Preparar información de zonas
    zonas = zonas.merge(
        datos["bodegas"][["id_bodega", "nombre"]],
        on="id_bodega",
        how="left"
    )

    return {
        "materiales": datos_materiales,
        "demanda": demanda,
        "zonas": zonas,
        "distribucion": datos["distribucion"],
        "servicio": datos["servicio"],
        "restricciones": datos["restricciones"],
        "costos_transferencia": datos["costos_transferencia"],
        "demanda_historica": datos["demanda_historica"]
    }


# =====================================================
# 5. MOSTRAR RESUMEN
# =====================================================

def mostrar_resumen(datos, parametros):

    print("\n======================================")
    print("       REM INVENTORY")
    print("       PREPARACIÓN DEL MODELO")
    print("======================================")

    print("\nINFORMACIÓN CARGADA")

    for nombre, tabla in datos.items():
        print(f"{nombre}: {len(tabla)} registros")

    print("\nPARÁMETROS DEL MODELO")

    print(
        "Materiales:",
        len(parametros["materiales"])
    )

    print(
        "Periodos de demanda:",
        parametros["demanda"]["periodo"].nunique()
    )

    print(
        "Zonas de almacenamiento:",
        len(parametros["zonas"])
    )

    print(
        "Bodegas:",
        parametros["zonas"]["id_bodega"].nunique()
    )

    print(
        "Asignaciones simuladas:",
        len(parametros["distribucion"])
    )

    print("\nCAPACIDAD DE LAS ZONAS")

    print(
        parametros["zonas"][
            [
                "nombre",
                "tipo_zona",
                "capacidad_m3",
                "capacidad_recepcion_kg_mes"
            ]
        ].to_string(index=False)
    )

    print("\nPREPARACIÓN FINALIZADA")


# =====================================================
# 6. EJECUCIÓN PRINCIPAL
# =====================================================

if __name__ == "__main__":

    try:

        print("Conectando con REM Inventory...")

        datos = cargar_tablas()

        print("Tablas cargadas correctamente.")

        errores = validar_datos(datos)

        if errores:

            print("\nSE ENCONTRARON PROBLEMAS:")

            for error in errores:
                print("-", error)

        else:

            parametros = preparar_parametros(datos)

            mostrar_resumen(datos, parametros)

    except Exception as error:

        print("\nERROR AL PREPARAR LOS DATOS:")
        print(error)

    finally:

        engine.dispose()

def mostrar_restricciones_financieras():

    datos = cargar_tablas()

    print("\n===== PARÁMETROS FINANCIEROS =====")

    print(
        datos["restricciones"][
            ["parametro", "valor", "descripcion"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    mostrar_restricciones_financieras()
