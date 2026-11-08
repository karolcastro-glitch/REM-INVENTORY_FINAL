
import os
import pandas as pd

from dotenv import load_dotenv
from sqlalchemy import create_engine, URL

# Cargar las variables de conexión
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

consulta = """
SELECT
    b.nombre AS bodega,
    z.id_zona,
    z.tipo_zona,
    i.cod_material,
    m.descripcion,
    i.cantidad_existente,
    m.volumen_m3_ud,
    m.peso_kg_ud
FROM inventario_por_zona i
INNER JOIN materiales m
    ON i.cod_material = m.cod_material
INNER JOIN zonas_almacenamiento z
    ON i.id_zona = z.id_zona
INNER JOIN bodegas b
    ON z.id_bodega = b.id_bodega
WHERE i.id_escenario = 1
  AND i.tipo_registro = 'SIMULACION'
ORDER BY b.nombre, z.id_zona, i.cod_material;
"""

try:
    df = pd.read_sql(consulta, engine)

    print("\n===== DISTRIBUCIÓN SIMULADA =====")
    print(df.to_string(index=False))

    print("\nTotal de registros:", len(df))
    print("Total de materiales:", df["cod_material"].nunique())
    print("Total de bodegas:", df["bodega"].nunique())

except Exception as error:
    print("Error al consultar la distribución:", error)

finally:
    engine.dispose()
