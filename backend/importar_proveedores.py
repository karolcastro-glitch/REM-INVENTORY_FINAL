
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

USUARIO = "root"
CONTRASENA = "rem_inventarios123"
HOST = "localhost"
PUERTO = "3306"
BASE_DATOS = "rem_inventory"

URL = (
    f"mysql+pymysql://{USUARIO}:{CONTRASENA}"
    f"@{HOST}:{PUERTO}/{BASE_DATOS}"
)

carpeta = Path(__file__).resolve().parent.parent / "data"

archivo = carpeta / "Etapa2_Bases_sinteticas_inventarios.xlsx"

df = pd.read_excel(
    archivo,
    sheet_name="04_proveedores"
)

engine = create_engine(URL)

try:
    with engine.begin() as conexion:

        conexion.execute(
            text("DELETE FROM proveedores_material")
        )

        df.to_sql(
            name="proveedores_material",
            con=conexion,
            if_exists="append",
            index=False
        )

    print("Importación de proveedores exitosa.")
    print("Registros importados:", len(df))

except Exception as error:
    print("Error durante la importación:")
    print(error)

finally:
    engine.dispose()
