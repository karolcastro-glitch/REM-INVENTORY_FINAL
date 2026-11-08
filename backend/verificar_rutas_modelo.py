from pathlib import Path

PROYECTO = Path(__file__).resolve().parent.parent
RUTA_ENTRADA = PROYECTO / "data"

ARCHIVO_BASES = RUTA_ENTRADA / "Etapa2_Bases_sinteticas_inventarios.xlsx"
ARCHIVO_ABC = RUTA_ENTRADA / "Etapa1_Matriz_ABC_multicriterio_SINTETICO.xlsx"

print("=" * 45)
print("VERIFICACIÓN DE RUTAS - REM INVENTORY")
print("=" * 45)

print("Proyecto:", PROYECTO)
print("Carpeta data:", RUTA_ENTRADA)
print("Excel de bases:", ARCHIVO_BASES.exists())
print("Excel ABC:", ARCHIVO_ABC.exists())

if ARCHIVO_BASES.exists() and ARCHIVO_ABC.exists():
    print("\nRutas verificadas correctamente.")
else:
    print("\nERROR: No se encontraron todos los archivos.")