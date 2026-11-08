
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# Cargar credenciales
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

# Consultar inventario disponible y características
consulta = text("""
    SELECT
        m.cod_material,
        m.descripcion,
        m.zona_almacen,
        m.peso_kg_ud,
        m.volumen_m3_ud,
        i.inventario_inicial,
        i.inventario_comprometido,
        i.inventario_disponible
    FROM materiales m
    INNER JOIN inventarios i
        ON m.cod_material = i.cod_material
    ORDER BY m.cod_material
""")

with engine.connect() as conexion:
    materiales = pd.read_sql(consulta, conexion)

# Unificar categorías
materiales["zona_almacen"] = materiales["zona_almacen"].replace({
    "PATIO": "PATIO_ABIERTO"
})

# Calcular volumen y peso disponibles
materiales["volumen_disponible_m3"] = (
    materiales["inventario_disponible"] *
    materiales["volumen_m3_ud"]
)

materiales["peso_disponible_kg"] = (
    materiales["inventario_disponible"] *
    materiales["peso_kg_ud"]
)

# Mostrar información
print("\n===== INVENTARIO DISPONIBLE =====")
print(materiales.to_string(index=False))

print("\n===== RESUMEN POR TIPO DE ZONA =====")

resumen = materiales.groupby("zona_almacen").agg(
    materiales=("cod_material", "count"),
    unidades_disponibles=("inventario_disponible", "sum"),
    volumen_total_m3=("volumen_disponible_m3", "sum"),
    peso_total_kg=("peso_disponible_kg", "sum")
)

print(resumen.to_string())

print("\nPreparación de datos completada.")
