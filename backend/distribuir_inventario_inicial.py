
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# =====================================================
# 1. CONEXIÓN A MYSQL
# =====================================================

load_dotenv()

url = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

engine = create_engine(url)

# =====================================================
# 2. CONSULTAR MATERIALES E INVENTARIO
# =====================================================

consulta_materiales = text("""
    SELECT
        m.cod_material,
        m.descripcion,
        m.zona_almacen,
        m.volumen_m3_ud,
        m.peso_kg_ud,
        i.inventario_disponible
    FROM materiales m
    INNER JOIN inventarios i
        ON m.cod_material = i.cod_material
    ORDER BY m.cod_material
""")

# =====================================================
# 3. CONSULTAR ZONAS DE ALMACENAMIENTO
# =====================================================

consulta_zonas = text("""
    SELECT
        b.nombre AS bodega,
        z.id_zona,
        z.tipo_zona,
        z.capacidad_m3,
        z.capacidad_recepcion_kg_mes
    FROM zonas_almacenamiento z
    INNER JOIN bodegas b
        ON z.id_bodega = b.id_bodega
    ORDER BY b.nombre, z.id_zona
""")

with engine.connect() as conexion:
    materiales = pd.read_sql(consulta_materiales, conexion)
    zonas = pd.read_sql(consulta_zonas, conexion)

# =====================================================
# 4. NORMALIZAR CATEGORÍAS
# =====================================================

materiales["zona_almacen"] = materiales["zona_almacen"].replace({
    "PATIO": "PATIO_ABIERTO"
})

# =====================================================
# 5. DISTRIBUIR PROPORCIONALMENTE
# =====================================================

distribucion = []

for _, material in materiales.iterrows():

    compatibles = zonas[
        zonas["tipo_zona"] == material["zona_almacen"]
    ].copy()

    if compatibles.empty:
        raise ValueError(
            f"No hay zonas compatibles para {material['cod_material']}"
        )

    cantidad_total = int(material["inventario_disponible"])

    # Proporción según la capacidad de cada zona compatible
    capacidad_total = compatibles["capacidad_m3"].sum()

    compatibles["proporcion"] = (
        compatibles["capacidad_m3"] / capacidad_total
    )

    compatibles["cantidad_exacta"] = (
        cantidad_total * compatibles["proporcion"]
    )

    compatibles["cantidad_asignada"] = (
        compatibles["cantidad_exacta"].apply(int)
    )

    # Repartir las unidades restantes por mayor decimal
    restantes = cantidad_total - compatibles["cantidad_asignada"].sum()

    compatibles["decimal"] = (
        compatibles["cantidad_exacta"]
        - compatibles["cantidad_asignada"]
    )

    indices = compatibles.sort_values(
        "decimal", ascending=False
    ).index.tolist()

    for indice in indices[:restantes]:
        compatibles.loc[indice, "cantidad_asignada"] += 1

    # Registrar las cantidades asignadas
    for _, zona in compatibles.iterrows():

        cantidad = int(zona["cantidad_asignada"])

        if cantidad == 0:
            continue

        distribucion.append({
            "cod_material": material["cod_material"],
            "descripcion": material["descripcion"],
            "bodega": zona["bodega"],
            "id_zona": zona["id_zona"],
            "tipo_zona": zona["tipo_zona"],
            "cantidad_asignada": cantidad,
            "volumen_m3": cantidad * material["volumen_m3_ud"],
            "peso_kg": cantidad * material["peso_kg_ud"],
            "capacidad_m3": zona["capacidad_m3"]
        })

# =====================================================
# 6. RESULTADOS Y VALIDACIONES
# =====================================================

resultado = pd.DataFrame(distribucion)

print("\n===== DISTRIBUCIÓN INICIAL PROPUESTA =====")
print(resultado.to_string(index=False))

resumen = resultado.groupby(
    ["bodega", "id_zona", "tipo_zona", "capacidad_m3"]
).agg(
    unidades=("cantidad_asignada", "sum"),
    volumen_ocupado_m3=("volumen_m3", "sum"),
    peso_total_kg=("peso_kg", "sum")
).reset_index()

resumen["ocupacion_porcentaje"] = (
    100 * resumen["volumen_ocupado_m3"] / resumen["capacidad_m3"]
)

print("\n===== RESUMEN DE OCUPACIÓN POR ZONA =====")
print(resumen.to_string(index=False))

# Comprobar que ninguna zona supere su capacidad
if (resumen["volumen_ocupado_m3"] > resumen["capacidad_m3"]).any():
    raise ValueError("ERROR: Una zona supera su capacidad.")

# Comprobar que se distribuyó todo el inventario disponible
total_distribuido = resultado.groupby(
    "cod_material"
)["cantidad_asignada"].sum()

total_original = materiales.set_index(
    "cod_material"
)["inventario_disponible"]

if not total_distribuido.equals(total_original.astype(int)):
    raise ValueError("ERROR: Las cantidades distribuidas no coinciden.")

print("\nVALIDACIONES SUPERADAS")
print("Todas las cantidades fueron distribuidas.")
print("Ninguna zona supera su capacidad.")
print("El inventario real de MySQL no fue modificado.")
