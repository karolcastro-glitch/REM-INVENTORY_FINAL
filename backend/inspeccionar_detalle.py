
from pathlib import Path
import pandas as pd

carpeta = Path(__file__).resolve().parent.parent / "data"

archivo = carpeta / "Etapa2_Bases_sinteticas_inventarios.xlsx"

hojas = [
    "02_maestro",
    "03_demanda_historica",
    "04_proveedores",
    "05_inventarios",
    "06_restricciones_financieras",
    "07_capacidad_almacen",
    "08_parametros_servicio",
    "09_demanda_horizonte"
]

for nombre_hoja in hojas:
    df = pd.read_excel(archivo, sheet_name=nombre_hoja)

    print("\n" + "=" * 70)
    print("HOJA:", nombre_hoja)
    print("=" * 70)

    print("\nTipos de datos:")
    print(df.dtypes)

    print("\nPrimeros 5 registros:")
    print(df.head().to_string(index=False))
