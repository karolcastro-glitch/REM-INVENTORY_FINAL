from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from threading import Lock
from pathlib import Path
from datetime import datetime
import pandas as pd
import traceback

from preparar_datos_modelo import cargar_tablas, validar_datos, engine
from optimizador_milp import resolver_optimizacion
from sqlalchemy import text


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

app = FastAPI(
    title="REM Inventory API",
    description="API del sistema de optimización de inventarios",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

CARPETA_BACKEND = Path(__file__).resolve().parent

ARCHIVOS_RESULTADOS = {
    "compras": "compras_optimizadas.csv",
    "mensuales": "resultados_mensuales_optimizados.csv",
    "indicadores": "indicadores_material_mes_optimizados.csv",
    "transferencias": "transferencias_optimizadas.csv",
    "transito": "pedidos_transito_sinteticos.csv"
}
CARPETA_RESULTADOS = CARPETA_BACKEND / "resultados"


# =========================================================
# ESTADO DE LA OPTIMIZACIÓN
# =========================================================

lock_optimizacion = Lock()
lock_actualizacion_inventario = Lock()

resultado_actual = None

estado_optimizacion = {
    "estado": "SIN_EJECUTAR",
    "mensaje": "Todavía no se ha ejecutado ninguna optimización.",
    "progreso": 0,
    "fecha_inicio": None,
    "fecha_fin": None,
    "nombre_escenario": None
}


# =========================================================
# MODELO DE ENTRADA
# =========================================================

class ParametrosOptimizacion(BaseModel):
    nombre_escenario: str = Field(
        default="Escenario base",
        min_length=1,
        max_length=100
    )

    presupuesto_mensual: float = Field(
        default=840000000,
        gt=0
    )


class RegistroInventario(BaseModel):
    cod_material: str = Field(min_length=1, max_length=50)
    cantidad: int = Field(gt=0, le=1_000_000)
    id_zona: int = Field(gt=0)


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def convertir_a_json(datos):
    """
    Convierte DataFrames, valores de Pandas y otros tipos
    a estructuras compatibles con JSON.
    """

    if isinstance(datos, pd.DataFrame):
        return datos.replace({float("nan"): None}).to_dict(orient="records")

    if isinstance(datos, dict):
        return {
            str(clave): convertir_a_json(valor)
            for clave, valor in datos.items()
        }

    if isinstance(datos, list):
        return [convertir_a_json(valor) for valor in datos]

    if hasattr(datos, "item"):
        try:
            return datos.item()
        except Exception:
            pass

    if pd.isna(datos) if not isinstance(datos, (dict, list, tuple)) else False:
        return None

    return datos


def obtener_columna(df, posibles_nombres):
    """
    Busca una columna usando varios nombres posibles.
    """

    if df is None or not isinstance(df, pd.DataFrame):
        return None

    for nombre in posibles_nombres:
        if nombre in df.columns:
            return nombre

    return None


def ejecutar_modelo_en_segundo_plano(
    presupuesto_mensual,
    nombre_escenario
):
    """
    Ejecuta el optimizador sin mantener bloqueada
    la petición HTTP del navegador.
    """

    global resultado_actual
    global estado_optimizacion

    try:
        with lock_optimizacion:
            estado_optimizacion["nombre_escenario"] = nombre_escenario
            estado_optimizacion["estado"] = "EJECUTANDO"
            estado_optimizacion["mensaje"] = (
                f"Buscando un plan factible para el escenario: {nombre_escenario}"
            )
            estado_optimizacion["progreso"] = 10
            estado_optimizacion["fecha_inicio"] = (
                datetime.now().isoformat()
            )
            estado_optimizacion["fecha_fin"] = None

        resultado = resolver_optimizacion(
            presupuesto_mensual_override=presupuesto_mensual
        )

        if resultado is None:
            with lock_optimizacion:
                resultado_actual = None
                estado_optimizacion["estado"] = "ERROR"
                estado_optimizacion["mensaje"] = (
                    "El optimizador terminó sin devolver un plan. Revisa los datos y las restricciones del escenario."
                )
                estado_optimizacion["progreso"] = 0
                estado_optimizacion["fecha_fin"] = datetime.now().isoformat()
            return

        with lock_optimizacion:
            resultado_actual = resultado

            estado_optimizacion["estado"] = "FINALIZADO"
            estado_optimizacion["mensaje"] = (
                "La optimización terminó correctamente."
            )
            estado_optimizacion["progreso"] = 100
            estado_optimizacion["fecha_fin"] = (
                datetime.now().isoformat()
            )

    except Exception as error:
        traceback.print_exc()

        with lock_optimizacion:
            estado_optimizacion["estado"] = "ERROR"
            estado_optimizacion["mensaje"] = str(error)
            estado_optimizacion["progreso"] = 0
            estado_optimizacion["fecha_fin"] = (
                datetime.now().isoformat()
            )


# =========================================================
# RUTAS GENERALES
# =========================================================

@app.get("/")
def inicio():
    return {
        "aplicacion": "REM Inventory",
        "mensaje": "API funcionando correctamente.",
        "version": "1.0.0"
    }


@app.get("/api/salud")
def salud():
    return {
        "estado": "OK",
        "mensaje": "La API está disponible."
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/api/dashboard")
def obtener_dashboard():
    try:
        datos = cargar_tablas()

        materiales = datos.get("materiales", pd.DataFrame())
        inventarios = datos.get("inventarios", pd.DataFrame())
        bodegas = datos.get("bodegas", pd.DataFrame())
        zonas = datos.get("zonas", pd.DataFrame())

        total_materiales = (
            len(materiales)
            if isinstance(materiales, pd.DataFrame)
            else 0
        )

        columna_cantidad = obtener_columna(
            inventarios,
            [
                "inventario_disponible",
                "cantidad_disponible",
                "cantidad_existente",
                "cantidad_actual",
                "stock_actual"
            ]
        )

        unidades_disponibles = 0

        if columna_cantidad:
            unidades_disponibles = float(
                pd.to_numeric(
                    inventarios[columna_cantidad],
                    errors="coerce"
                ).fillna(0).sum()
            )

        capacidad_total = 0

        if isinstance(zonas, pd.DataFrame):
            columna_capacidad = obtener_columna(
                zonas,
                ["capacidad_m3"]
            )

            if columna_capacidad:
                capacidad_total = float(
                    pd.to_numeric(
                        zonas[columna_capacidad],
                        errors="coerce"
                    ).fillna(0).sum()
                )

        with lock_optimizacion:
            estado_actual = estado_optimizacion["estado"]

        return {
            "materiales": total_materiales,
            "unidades_disponibles": unidades_disponibles,
            "capacidad_total_m3": capacidad_total,
            "cantidad_bodegas": (
                len(bodegas)
                if isinstance(bodegas, pd.DataFrame)
                else 0
            ),
            "cantidad_zonas": (
                len(zonas)
                if isinstance(zonas, pd.DataFrame)
                else 0
            ),
            "estado_optimizacion": estado_actual
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al cargar el dashboard: {str(error)}"
        )


# =========================================================
# MATERIALES
# =========================================================

@app.get("/api/materiales")
def obtener_materiales():
    try:
        datos = cargar_tablas()
        materiales = datos.get("materiales", pd.DataFrame())

        return convertir_a_json(materiales)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar materiales: {str(error)}"
        )


@app.get("/api/datos-base")
def obtener_datos_base():
    """Entrega catálogo, existencias y asignación del escenario base."""
    try:
        datos = cargar_tablas()
        materiales = datos.get("materiales", pd.DataFrame()).copy()
        inventarios = datos.get("inventarios", pd.DataFrame()).copy()
        distribucion = datos.get("distribucion", pd.DataFrame()).copy()

        if materiales.empty:
            return {"materiales": []}

        base = materiales.merge(inventarios, on="cod_material", how="left")
        if not distribucion.empty:
            columnas = [
                c for c in ("cod_material", "id_zona", "cantidad_existente")
                if c in distribucion.columns
            ]
            base = base.merge(distribucion[columnas], on="cod_material", how="left")
            base = base.rename(columns={"cantidad_existente": "cantidad_en_zona"})
        return {"materiales": convertir_a_json(base)}
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al cargar el catálogo de inventario: {str(error)}"
        )


@app.post("/api/inventario")
def agregar_inventario(registro: RegistroInventario):
    with lock_actualizacion_inventario:
        with lock_optimizacion:
            if estado_optimizacion["estado"] == "EJECUTANDO":
                raise HTTPException(
                    status_code=409,
                    detail="Espera a que termine la optimización antes de modificar el inventario."
                )
        return _registrar_inventario(registro)


def _registrar_inventario(registro: RegistroInventario):
    """Suma existencias operativas y las asigna a una zona del escenario base."""
    global resultado_actual, estado_optimizacion

    codigo = registro.cod_material.strip()
    cantidad = registro.cantidad

    try:
        with engine.begin() as conexion:
            material = conexion.execute(
                text("""
                    SELECT cod_material, zona_almacen, volumen_m3_ud
                    FROM materiales
                    WHERE cod_material = :codigo
                    FOR UPDATE
                """),
                {"codigo": codigo}
            ).mappings().first()
            if not material:
                raise HTTPException(status_code=404, detail="El material seleccionado no existe.")

            inventario = conexion.execute(
                text("""
                    SELECT id_inventario, inventario_inicial,
                           inventario_comprometido, inventario_disponible
                    FROM inventarios
                    WHERE cod_material = :codigo
                    FOR UPDATE
                """),
                {"codigo": codigo}
            ).mappings().all()
            if len(inventario) != 1:
                raise HTTPException(
                    status_code=409,
                    detail="El material debe tener exactamente un registro de inventario para poder actualizarse."
                )

            zona = conexion.execute(
                text("""
                    SELECT id_zona, tipo_zona, capacidad_m3
                    FROM zonas_almacenamiento
                    WHERE id_zona = :id_zona
                """),
                {"id_zona": registro.id_zona}
            ).mappings().first()
            if not zona:
                raise HTTPException(status_code=404, detail="La zona seleccionada no existe.")

            normalizar = lambda valor: (
                "PATIO_ABIERTO" if str(valor).strip().upper() in ("PATIO", "PATIO_ABIERTO", "ABIERTO")
                else "CUBIERTA" if str(valor).strip().upper() in ("CUBIERTA", "TECHADA")
                else str(valor).strip().upper()
            )
            if normalizar(material["zona_almacen"]) != normalizar(zona["tipo_zona"]):
                raise HTTPException(
                    status_code=422,
                    detail="La zona elegida no es compatible con el almacenamiento requerido por el material."
                )

            existentes = conexion.execute(
                text("""
                    SELECT iz.id_zona, iz.cantidad_existente, m.volumen_m3_ud
                    FROM inventario_por_zona iz
                    JOIN materiales m ON m.cod_material = iz.cod_material
                    WHERE iz.tipo_registro = 'SIMULACION'
                      AND iz.id_escenario = 1
                      AND iz.id_zona = :id_zona
                """),
                {"id_zona": registro.id_zona}
            ).mappings().all()
            ocupacion = sum(
                float(fila["cantidad_existente"] or 0) * float(fila["volumen_m3_ud"] or 0)
                for fila in existentes
            )
            volumen_adicional = cantidad * float(material["volumen_m3_ud"] or 0)
            capacidad_zona = float(zona["capacidad_m3"] or 0)
            if ocupacion + volumen_adicional > capacidad_zona + 1e-9:
                raise HTTPException(
                    status_code=422,
                    detail=f"La cantidad excede la capacidad de la zona elegida ({capacidad_zona:,.2f} m³)."
                )

            fila = inventario[0]
            existencias_zona = conexion.execute(
                text("""
                    SELECT COALESCE(SUM(cantidad_existente - COALESCE(cantidad_comprometida, 0)), 0)
                    FROM inventario_por_zona
                    WHERE cod_material = :codigo
                      AND tipo_registro = 'SIMULACION'
                      AND id_escenario = 1
                """),
                {"codigo": codigo}
            ).scalar_one()
            if abs(float(existencias_zona or 0) - float(fila["inventario_disponible"] or 0)) > 1e-4:
                raise HTTPException(
                    status_code=409,
                    detail="La distribución del escenario base no coincide con el inventario disponible. Corrige la distribución antes de agregar unidades."
                )

            # El maestro guarda la existencia operativa; el optimizador parte
            # de la asignación SIMULACION por zona, que debe conservar el mismo total.
            conexion.execute(
                text("""
                    UPDATE inventarios
                    SET inventario_inicial = inventario_inicial + :cantidad,
                        inventario_disponible = inventario_disponible + :cantidad
                    WHERE id_inventario = :id_inventario
                """),
                {"cantidad": cantidad, "id_inventario": fila["id_inventario"]}
            )

            ubicacion = conexion.execute(
                text("""
                    SELECT id_inventario_zona, cantidad_existente
                    FROM inventario_por_zona
                    WHERE cod_material = :codigo
                      AND id_zona = :id_zona
                      AND tipo_registro = 'SIMULACION'
                      AND id_escenario = 1
                    FOR UPDATE
                """),
                {"codigo": codigo, "id_zona": registro.id_zona}
            ).mappings().all()
            if len(ubicacion) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="Hay asignaciones duplicadas del material en esa zona; corrige los datos antes de continuar."
                )
            if ubicacion:
                conexion.execute(
                    text("""
                        UPDATE inventario_por_zona
                        SET cantidad_existente = cantidad_existente + :cantidad
                        WHERE id_inventario_zona = :id
                    """),
                    {"cantidad": cantidad, "id": ubicacion[0]["id_inventario_zona"]}
                )
            else:
                conexion.execute(
                    text("""
                        INSERT INTO inventario_por_zona
                            (cod_material, id_zona, cantidad_existente,
                             cantidad_comprometida, tipo_registro, id_escenario)
                        VALUES (:codigo, :id_zona, :cantidad, 0, 'SIMULACION', 1)
                    """),
                    {"codigo": codigo, "id_zona": registro.id_zona, "cantidad": cantidad}
                )

        with lock_optimizacion:
            resultado_actual = None
            estado_optimizacion = {
                "estado": "SIN_EJECUTAR",
                "mensaje": "Inventario actualizado. Ejecuta una nueva optimización para ver su efecto.",
                "progreso": 0,
                "fecha_inicio": None,
                "fecha_fin": None,
                "nombre_escenario": None
            }

        return {
            "mensaje": f"Se agregaron {cantidad:,} unidades de {codigo} al inventario operativo.",
            "cantidad_agregada": cantidad,
            "cod_material": codigo,
            "id_zona": registro.id_zona,
            "siguiente_paso": "Ejecuta de nuevo la optimización para incorporar el cambio al plan."
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"No fue posible actualizar el inventario: {str(error)}"
        )


# =========================================================
# ZONAS DE ALMACENAMIENTO
# =========================================================

@app.get("/api/zonas")
def obtener_zonas():
    try:
        datos = cargar_tablas()
        zonas = datos.get("zonas", pd.DataFrame()).copy()
        bodegas = datos.get("bodegas", pd.DataFrame())
        if (
            not zonas.empty
            and isinstance(bodegas, pd.DataFrame)
            and {"id_bodega", "nombre"}.issubset(bodegas.columns)
        ):
            zonas = zonas.merge(
                bodegas[["id_bodega", "nombre"]].drop_duplicates("id_bodega"),
                on="id_bodega",
                how="left"
            ).rename(columns={"nombre": "nombre_bodega"})

        return convertir_a_json(zonas)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar zonas: {str(error)}"
        )


# =========================================================
# INICIAR OPTIMIZACIÓN
# =========================================================

@app.post("/api/optimizar")
def iniciar_optimizacion(
    parametros: ParametrosOptimizacion,
    background_tasks: BackgroundTasks
):
    global estado_optimizacion, resultado_actual

    with lock_optimizacion:

        if lock_actualizacion_inventario.locked():
            raise HTTPException(
                status_code=409,
                detail="Espera a que termine la actualización del inventario antes de iniciar la optimización."
            )

        if estado_optimizacion["estado"] == "EJECUTANDO":
            raise HTTPException(
                status_code=409,
                detail="Ya existe una optimización en ejecución."
            )

        estado_optimizacion = {
            "estado": "EJECUTANDO",
            "mensaje": "La optimización está comenzando.",
            "progreso": 5,
            "fecha_inicio": datetime.now().isoformat(),
            "fecha_fin": None,
            "nombre_escenario": parametros.nombre_escenario
        }
        resultado_actual = None

    background_tasks.add_task(
        ejecutar_modelo_en_segundo_plano,
        parametros.presupuesto_mensual,
        parametros.nombre_escenario
    )

    return {
        "estado": "EJECUTANDO",
        "mensaje": "La optimización se inició correctamente.",
        "nombre_escenario": parametros.nombre_escenario
    }


# =========================================================
# CONSULTAR ESTADO
# =========================================================

@app.get("/api/estado-optimizacion")
def consultar_estado():
    with lock_optimizacion:
        return estado_optimizacion.copy()


# =========================================================
# CONSULTAR RESULTADOS
# =========================================================

@app.get("/api/resultados")
def obtener_resultados():
    with lock_optimizacion:
        estado = estado_optimizacion["estado"]
        resultado = resultado_actual

    if estado == "EJECUTANDO":
        raise HTTPException(
            status_code=202,
            detail="La optimización todavía está en ejecución."
        )

    if estado == "ERROR":
        raise HTTPException(
            status_code=500,
            detail=estado_optimizacion["mensaje"]
        )

    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Todavía no hay resultados de optimización disponibles."
        )

    return convertir_a_json(resultado)


# =========================================================
# DESCARGAR ARCHIVOS CSV
# =========================================================

@app.get("/api/archivos-resultados")
def listar_archivos_resultados():
    archivos = {}

    for clave, nombre_archivo in ARCHIVOS_RESULTADOS.items():
        ruta = CARPETA_RESULTADOS / nombre_archivo

        archivos[clave] = {
            "disponible": ruta.exists(),
            "nombre": nombre_archivo
        }

    return archivos


@app.get("/api/archivos-resultados/{tipo}")
def descargar_archivo_resultado(tipo: str):
    from fastapi.responses import FileResponse

    if tipo not in ARCHIVOS_RESULTADOS:
        raise HTTPException(
            status_code=404,
            detail="Tipo de archivo no válido."
        )

    nombre_archivo = ARCHIVOS_RESULTADOS[tipo]
    ruta = CARPETA_RESULTADOS / nombre_archivo

    if not ruta.exists():
        raise HTTPException(
            status_code=404,
            detail="El archivo todavía no está disponible."
        )

    return FileResponse(
        path=str(ruta),
        filename=nombre_archivo,
        media_type="text/csv"
    )
