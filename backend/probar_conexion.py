
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os

load_dotenv()

conexion_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

try:
    engine = create_engine(conexion_url)

    with engine.connect() as conexion:
        resultado = conexion.execute(text("SELECT DATABASE();"))

        print("¡Conexión exitosa!")
        print("Base de datos:", resultado.scalar())

except Exception as error:
    print("No se pudo conectar a MySQL.")
    print("Detalle:", error)
