
from pathlib import Path
import pandas as pd

# Ubicación de la carpeta data
carpeta_data = Path(__file__).resolve().parent.parent / "data"

print("=" * 60)
print("       REM INVENTORY - INSPECCIÓN DE EXCEL")
print("=" * 60)

archivos = list(carpeta_data.glob("*.xlsx"))

if not archivos:
    print("No se encontraron archivos Excel en la carpeta data.")
else:
    for archivo in archivos:
        print(f"\nARCHIVO: {archivo.name}")
        print("-" * 60)

        excel = pd.ExcelFile(archivo)

        for hoja in excel.sheet_names:
            df = pd.read_excel(archivo, sheet_name=hoja)

            print(f"\nHoja: {hoja}")
            print(f"Cantidad de registros: {len(df)}")
            print("Columnas:")

            for columna in df.columns:
                print(f"  - {columna}")

print("\nInspección finalizada.")
