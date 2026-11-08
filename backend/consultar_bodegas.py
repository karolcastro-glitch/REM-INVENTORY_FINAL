
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os

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

consulta = text("""
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
    resultados = conexion.execute(consulta)

    for fila in resultados:
        print(
            fila.bodega,
            fila.id_zona,
            fila.tipo_zona,
            fila.capacidad_m3,
            fila.capacidad_recepcion_kg_mes
        )
