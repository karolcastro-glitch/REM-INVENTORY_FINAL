
from pathlib import Path
from openpyxl import load_workbook

# Rutas del proyecto
CARPETA_BACKEND = Path(__file__).resolve().parent
ARCHIVO_EXCEL = (
    CARPETA_BACKEND.parent
    / "data"
    / "Etapa6_Modelo_MILP_codigo_y_resultados_SINTETICO.xlsx"
)

ARCHIVO_SALIDA = (
    CARPETA_BACKEND
    / "modelo_original"
    / "modelo_milp_original.py"
)

try:
    libro = load_workbook(ARCHIVO_EXCEL, data_only=True)

    hoja = libro["Codigo_Python"]

    lineas = []

    for fila in hoja.iter_rows(min_row=2, max_col=1, values_only=True):
        contenido = fila[0]

        if contenido is None:
            lineas.append("")
        else:
            lineas.append(str(contenido))

    codigo = "\n".join(lineas)

    ARCHIVO_SALIDA.write_text(codigo, encoding="utf-8")

    print("Código original extraído correctamente.")
    print("Líneas extraídas:", len(lineas))
    print("Archivo:", ARCHIVO_SALIDA)

except Exception as error:
    print("Error durante la extracción:", error)
