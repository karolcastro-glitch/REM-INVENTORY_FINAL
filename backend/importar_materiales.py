
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

# 1. Configuración de conexión
USUARIO = "root"
CONTRASENA = "rem_inventarios123"
HOST = "localhost"
PUERTO = "3306"
BASE_DATOS = "rem_inventory"

URL = (
    f"mysql+pymysql://{USUARIO}:{CONTRASENA}"
    f"@{HOST}:{PUERTO}/{BASE_DATOS}"
)

# 2. Ubicación del Excel
carpeta = Path(__file__).resolve().parent.parent / "data"

archivo = carpeta / "Etapa2_Bases_sinteticas_inventarios.xlsx"

# 3. Leer hoja del maestro
df = pd.read_excel(
    archivo,
    sheet_name="02_maestro"
)

# 4. Conectar e importar
engine = create_engine(URL)

try:
    with engine.begin() as conexion:

        # Evitar duplicar registros
        conexion.execute(
            text("DELETE FROM materiales")
        )

        df.to_sql(
            name="materiales",
            con=conexion,
            if_exists="append",
            index=False
        )

    print("Importación exitosa.")
    print("Materiales importados:", len(df))

except Exception as error:
    print("Error durante la importación:")
    print(error)

finally:
    engine.dispose()
