
import pandas as pd
from sqlalchemy import create_engine
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

consulta = """
SELECT
    cod_material,
    descripcion,
    zona_almacen,
    peso_kg_ud,
    volumen_m3_ud,
    criticidad
FROM materiales
ORDER BY cod_material;
"""

materiales = pd.read_sql(consulta, engine)

# Unificar los nombres de las zonas
materiales["zona_almacen"] = materiales["zona_almacen"].replace({
    "PATIO": "PATIO_ABIERTO"
})

print("MATERIALES Y ZONAS PERMITIDAS")
print(materiales.to_string(index=False))

print("\nTotal de materiales:", len(materiales))
