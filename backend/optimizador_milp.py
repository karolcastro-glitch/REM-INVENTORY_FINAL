from pathlib import Path
import math
import re

import pandas as pd
import pulp

from preparar_datos_modelo import cargar_tablas, validar_datos


# ============================================================
# CONFIGURACION
# ============================================================

ID_ESCENARIO = 1
TIEMPO_MEJORA_SEGUNDOS = 10
BRECHA_RELATIVA = 0.01
VER_LOG_SOLVER = True

CARPETA_BACKEND = Path(__file__).resolve().parent
CARPETA_RESULTADOS = CARPETA_BACKEND / "resultados"
CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def numero(valor, defecto=0.0):
    if valor is None or pd.isna(valor):
        return float(defecto)
    return float(valor)


def normalizar_zona(valor):
    texto = str(valor).strip().upper()
    if texto in ("PATIO", "PATIO_ABIERTO", "ABIERTO"):
        return "PATIO_ABIERTO"
    if texto in ("CUBIERTA", "TECHADA"):
        return "CUBIERTA"
    return texto


def nombre_seguro(valor):
    return re.sub(r"[^A-Za-z0-9_]", "_", str(valor))


def obtener_parametro(df, nombre, defecto=None):
    if df is None or df.empty:
        if defecto is None:
            raise ValueError(f"Falta el parametro financiero: {nombre}")
        return float(defecto)

    filas = df[df["parametro"].astype(str).str.strip() == nombre]
    if filas.empty:
        if defecto is None:
            raise ValueError(f"No se encontro el parametro: {nombre}")
        return float(defecto)

    return numero(filas.iloc[0]["valor"])


# ============================================================
# PREPARACION DE DATOS
# ============================================================

def preparar_datos(datos):
    validar_datos(datos)

    materiales = datos["materiales"].copy()
    inventarios = datos["inventarios"].copy()
    demanda_df = datos["demanda_pronosticada"].copy()
    proveedores = datos["proveedores"].copy()
    servicio_df = datos["servicio"].copy()
    restricciones = datos["restricciones"].copy()
    zonas = datos["zonas"].copy()
    distribucion = datos["distribucion"].copy()
    transferencias_df = datos.get(
        "costos_transferencia", pd.DataFrame()
    ).copy()

    for nombre, tabla in {
        "materiales": materiales,
        "inventarios": inventarios,
        "demanda_pronosticada": demanda_df,
        "proveedores": proveedores,
        "servicio": servicio_df,
        "restricciones": restricciones,
        "zonas": zonas,
        "distribucion": distribucion,
    }.items():
        if tabla is None or tabla.empty:
            raise ValueError(f"La tabla {nombre} esta vacia.")

    base = materiales.merge(
        inventarios,
        on="cod_material",
        how="inner",
        validate="one_to_one"
    )

    base = base.merge(
        proveedores,
        on="cod_material",
        how="left",
        validate="one_to_one"
    )

    if "zona_almacen" not in base.columns:
        raise ValueError("Falta la columna zona_almacen en materiales.")

    base["zona_compatible"] = base["zona_almacen"].apply(
        normalizar_zona
    )

    zonas_validas = {"CUBIERTA", "PATIO_ABIERTO"}

    if not set(base["zona_compatible"]).issubset(zonas_validas):
        raise ValueError("Existe una zona de almacenamiento no reconocida.")

    if "tiempo_reposicion_meses" in base.columns:
        base["lead_meses"] = base["tiempo_reposicion_meses"].apply(
            lambda x: max(0, int(math.ceil(numero(x))))
        )
    elif "tiempo_reposicion_dias" in base.columns:
        base["lead_meses"] = base["tiempo_reposicion_dias"].apply(
            lambda x: max(0, int(math.ceil(numero(x) / 30)))
        )
    else:
        raise ValueError(
            "No existe el tiempo de reposicion del proveedor."
        )

    demanda_df["periodo"] = demanda_df["periodo"].astype(str)
    periodos = sorted(demanda_df["periodo"].unique().tolist())

    if len(periodos) != 12:
        raise ValueError(
            f"Se esperaban 12 periodos de demanda "
            f"y se encontraron {len(periodos)}."
        )

    mapa_mes = {
        p: t for t, p in enumerate(periodos, start=1)
    }

    demanda_df["mes"] = demanda_df["periodo"].map(mapa_mes)
    demanda = {}

    for _, fila in demanda_df.iterrows():
        codigo = fila["cod_material"]
        mes = int(fila["mes"])
        cantidad = numero(fila["demanda_pronosticada"])

        if cantidad < 0:
            raise ValueError(
                f"Demanda negativa para {codigo}, mes {mes}."
            )

        demanda[(codigo, mes)] = int(round(cantidad))

    servicio = {}

    for _, fila in servicio_df.iterrows():
        criticidad = str(fila["criticidad"]).strip().upper()
        nivel = numero(fila["nivel_servicio"])

        if nivel > 1:
            nivel /= 100

        servicio[criticidad] = {
            "nivel": min(max(nivel, 0.0), 1.0),
            "factor": max(
                1.0,
                numero(
                    fila.get("factor_penalizacion_faltante", 10),
                    10
                )
            )
        }

    zonas["id_zona"] = zonas["id_zona"].astype(int)
    zonas["tipo_zona_norm"] = zonas["tipo_zona"].apply(
        normalizar_zona
    )

    requeridas = [
        "id_zona",
        "id_bodega",
        "tipo_zona_norm",
        "capacidad_m3",
        "capacidad_recepcion_kg_mes"
    ]

    for col in requeridas:
        if col not in zonas.columns:
            raise ValueError(
                f"Falta la columna {col} en zonas_almacenamiento."
            )

    if "id_escenario" in distribucion.columns:
        distribucion = distribucion[
            distribucion["id_escenario"] == ID_ESCENARIO
        ].copy()

    if "tipo_registro" in distribucion.columns:
        distribucion = distribucion[
            distribucion["tipo_registro"].astype(str).str.upper()
            == "SIMULACION"
        ].copy()

    if distribucion.empty:
        raise ValueError(
            f"No hay distribucion SIMULACION "
            f"para el escenario {ID_ESCENARIO}."
        )

    columnas_ruta = {
        "id_zona_origen",
        "id_zona_destino",
        "costo_fijo_cop",
        "costo_por_kg_cop",
        "tiempo_translado_dias",
        "estado"
    }

    if transferencias_df.empty:
        raise ValueError(
            "La tabla costos_transferencia no contiene rutas."
        )

    faltan = columnas_ruta - set(transferencias_df.columns)

    if faltan:
        raise ValueError(
            "Faltan columnas en costos_transferencia: "
            + ", ".join(sorted(faltan))
        )

    transferencias_df = transferencias_df[
        pd.to_numeric(
            transferencias_df["estado"],
            errors="coerce"
        ).fillna(0) == 1
    ].copy()

    if transferencias_df.empty:
        raise ValueError(
            "No hay rutas de transferencia habilitadas."
        )

    for col in ["id_zona_origen", "id_zona_destino"]:
        transferencias_df[col] = pd.to_numeric(
            transferencias_df[col],
            errors="raise"
        ).astype(int)

    for col in [
        "costo_fijo_cop",
        "costo_por_kg_cop",
        "tiempo_translado_dias"
    ]:
        transferencias_df[col] = pd.to_numeric(
            transferencias_df[col],
            errors="raise"
        ).fillna(0)

    if (
        transferencias_df[
            ["costo_fijo_cop", "costo_por_kg_cop"]
        ] < 0
    ).any().any():
        raise ValueError(
            "Los costos de transferencia no pueden ser negativos."
        )

    if transferencias_df.duplicated(
        ["id_zona_origen", "id_zona_destino"]
    ).any():
        raise ValueError(
            "Hay rutas de transferencia duplicadas."
        )

    mapa_zonas = zonas.set_index("id_zona").to_dict("index")

    for _, ruta in transferencias_df.iterrows():
        zo = int(ruta["id_zona_origen"])
        zd = int(ruta["id_zona_destino"])

        if zo not in mapa_zonas or zd not in mapa_zonas or zo == zd:
            raise ValueError(
                f"Ruta de transferencia invalida: {zo} -> {zd}."
            )

        if (
            mapa_zonas[zo]["tipo_zona_norm"]
            != mapa_zonas[zd]["tipo_zona_norm"]
        ):
            raise ValueError(
                f"Ruta incompatible entre zonas {zo} y {zd}."
            )

    if "cantidad_existente" not in distribucion.columns:
        raise ValueError(
            "La distribucion no contiene cantidad_existente."
        )

    if "cantidad_comprometida" not in distribucion.columns:
        distribucion["cantidad_comprometida"] = 0

    distribucion["cantidad_existente"] = pd.to_numeric(
        distribucion["cantidad_existente"],
        errors="coerce"
    ).fillna(0)

    distribucion["cantidad_comprometida"] = pd.to_numeric(
        distribucion["cantidad_comprometida"],
        errors="coerce"
    ).fillna(0)

    distribucion["cantidad_disponible_zona"] = (
        distribucion["cantidad_existente"]
        - distribucion["cantidad_comprometida"]
    )

    if (
        distribucion["cantidad_disponible_zona"] < -1e-6
    ).any():
        raise ValueError(
            "Hay compromisos mayores que el inventario de una zona."
        )

    distribucion["cantidad_disponible_zona"] = (
        distribucion["cantidad_disponible_zona"].clip(lower=0)
    )

    columnas_zona_merge = [
        "id_zona",
        "id_bodega",
        "tipo_zona_norm",
        "capacidad_m3",
        "capacidad_recepcion_kg_mes"
    ]

    repetidas = [
        c for c in columnas_zona_merge
        if c != "id_zona" and c in distribucion.columns
    ]

    if repetidas:
        distribucion = distribucion.drop(columns=repetidas)

    distribucion = distribucion.merge(
        zonas[columnas_zona_merge],
        on="id_zona",
        how="left",
        validate="many_to_one"
    )

    if distribucion["tipo_zona_norm"].isna().any():
        raise ValueError(
            "La distribucion contiene una zona inexistente."
        )

    sumas = distribucion.groupby(
        "cod_material"
    )["cantidad_disponible_zona"].sum()

    for _, fila in base.iterrows():
        codigo = fila["cod_material"]
        disponible = numero(fila["inventario_disponible"])
        asignado = numero(sumas.get(codigo, 0))

        if abs(disponible - asignado) > 1e-4:
            raise ValueError(
                f"{codigo}: distribucion por zonas={asignado}, "
                f"inventario_disponible={disponible}."
            )

        incompatibles = distribucion[
            (distribucion["cod_material"] == codigo)
            & (distribucion["cantidad_disponible_zona"] > 0)
            & (
                distribucion["tipo_zona_norm"]
                != fila["zona_compatible"]
            )
        ]

        if not incompatibles.empty:
            raise ValueError(
                f"{codigo} tiene inventario en una zona incompatible."
            )

    return (
        base,
        demanda,
        periodos,
        servicio,
        zonas,
        distribucion,
        restricciones,
        transferencias_df
    )


# ============================================================
# PEDIDOS EN TRANSITO SINTETICOS
# ============================================================

def calcular_pedidos_en_transito(
    materiales,
    meses,
    demanda,
    inv_inicial,
    zonas_compatibles,
    costo,
    costo_pedido,
    minimo,
    multiplo,
    max_pedidos,
    lead,
    stock_seguridad
):
    transito_total = {}
    transito_zona = {}

    for i in materiales:
        demanda_anual = sum(
            demanda.get((i, t), 0) for t in meses
        )

        H = 0.22 * costo[i]

        if H <= 0:
            raise ValueError(
                f"Costo de mantenimiento invalido para {i}."
            )

        if demanda_anual > 0 and costo_pedido[i] > 0:
            eoq = math.sqrt(
                2 * demanda_anual * costo_pedido[i] / H
            )
        else:
            eoq = 0

        q_base = max(
            eoq,
            minimo[i],
            demanda_anual / max(1, max_pedidos[i])
        )

        q_ajustado = (
            math.ceil(q_base / multiplo[i]) * multiplo[i]
            if q_base > 0 else 0
        )

        inventario_proyectado = sum(
            inv_inicial[(i, z)]
            for z in zonas_compatibles[i]
        )

        for t in meses:
            if t > lead[i]:
                break

            d = demanda.get((i, t), 0)
            llegada = 0

            if (
                inventario_proyectado - d
                < stock_seguridad[i]
            ):
                deficit = stock_seguridad[i] - (
                    inventario_proyectado - d
                )

                lote = max(q_ajustado, deficit)
                lote = (
                    math.ceil(lote / multiplo[i]) * multiplo[i]
                )

                llegada = int(lote)

            transito_total[(i, t)] = llegada
            inventario_proyectado += llegada
            inventario_proyectado -= d

        for t in meses:
            cantidad = transito_total.get((i, t), 0)

            if cantidad <= 0:
                continue

            zs = zonas_compatibles[i]

            total_stock = sum(
                inv_inicial[(i, z)] for z in zs
            )

            if total_stock > 0:
                proporciones = {
                    z: inv_inicial[(i, z)] / total_stock
                    for z in zs
                }
            else:
                proporciones = {
                    z: 1 / len(zs) for z in zs
                }

            asignacion = {
                z: int(math.floor(
                    cantidad * proporciones[z]
                ))
                for z in zs
            }

            restante = cantidad - sum(asignacion.values())

            orden = sorted(
                zs,
                key=lambda z: (
                    cantidad * proporciones[z] - asignacion[z]
                ),
                reverse=True
            )

            for z in orden[:restante]:
                asignacion[z] += 1

            for z in zs:
                transito_zona[(i, t, z)] = asignacion[z]

    return transito_total, transito_zona


# ============================================================
# OPTIMIZACION
# ============================================================

def resolver_optimizacion(presupuesto_mensual_override=None):
    print("\n==============================================")
    print("             REM INVENTORY")
    print("       MOTOR DE OPTIMIZACION MILP")
    print("==============================================\n")

    print("Cargando datos desde MySQL...")
    datos = cargar_tablas()

    (
        base, demanda, periodos, servicio,
        zonas, distribucion, restricciones, transferencias_df
    ) = preparar_datos(datos)

    presupuesto_mensual = (
        float(presupuesto_mensual_override)
        if presupuesto_mensual_override is not None
        else obtener_parametro(
            restricciones, "presupuesto_compras_mensual_cop"
        )
    )

    presupuesto_anual = obtener_parametro(
        restricciones, "presupuesto_compras_anual_cop"
    )

    capital_maximo = obtener_parametro(
        restricciones, "limite_inversion_inventario_cop"
    )

    tasa_mantener_anual = obtener_parametro(
        restricciones, "tasa_costo_mantener_anual"
    )

    meses = list(range(1, 13))
    materiales = base["cod_material"].tolist()
    zonas_ids = zonas["id_zona"].astype(int).tolist()

    filas_material = base.set_index("cod_material").to_dict("index")
    filas_zona = zonas.set_index("id_zona").to_dict("index")

    rutas_transferencia = {}

    for _, ruta in transferencias_df.iterrows():
        clave = (
            int(ruta["id_zona_origen"]),
            int(ruta["id_zona_destino"])
        )

        rutas_transferencia[clave] = {
            "costo_fijo": numero(ruta["costo_fijo_cop"]),
            "costo_kg": numero(ruta["costo_por_kg_cop"]),
            "dias": int(round(
                numero(ruta["tiempo_translado_dias"])
            ))
        }

    zonas_compatibles = {
        i: [
            z for z in zonas_ids
            if filas_zona[z]["tipo_zona_norm"]
            == filas_material[i]["zona_compatible"]
        ]
        for i in materiales
    }

    for i in materiales:
        if not zonas_compatibles[i]:
            raise ValueError(f"No hay zona compatible para {i}.")

    inv_inicial = {}

    for i in materiales:
        for z in zonas_compatibles[i]:
            filas = distribucion[
                (distribucion["cod_material"] == i)
                & (distribucion["id_zona"] == z)
            ]

            inv_inicial[(i, z)] = int(round(
                filas["cantidad_disponible_zona"].sum()
            ))

    costo = {
        i: numero(filas_material[i]["costo_unitario_cop"])
        for i in materiales
    }

    peso = {
        i: numero(filas_material[i]["peso_kg_ud"])
        for i in materiales
    }

    volumen = {
        i: numero(filas_material[i]["volumen_m3_ud"])
        for i in materiales
    }

    costo_pedido = {
        i: numero(filas_material[i].get("costo_pedido_cop", 0))
        for i in materiales
    }

    minimo = {
        i: max(0, int(math.ceil(numero(
            filas_material[i].get("cantidad_minima_pedido", 0)
        ))))
        for i in materiales
    }

    multiplo = {
        i: max(1, int(round(numero(
            filas_material[i].get("multiplo_compra", 1), 1
        ))))
        for i in materiales
    }

    max_pedidos = {
        i: max(1, int(round(numero(
            filas_material[i].get("max_pedidos_anio", 12), 12
        ))))
        for i in materiales
    }

    lead = {
        i: int(filas_material[i]["lead_meses"])
        for i in materiales
    }

    stock_seguridad = {
        i: max(0, int(math.ceil(numero(
            filas_material[i].get("inventario_seguridad", 0)
        ))))
        for i in materiales
    }

    nivel_servicio = {}
    factor_penalizacion = {}

    for i in materiales:
        criticidad = str(
            filas_material[i].get("criticidad", "MEDIA")
        ).strip().upper()

        p = servicio.get(
            criticidad, {"nivel": 0.95, "factor": 10}
        )

        nivel_servicio[i] = p["nivel"]
        factor_penalizacion[i] = p["factor"]

    for i in materiales:
        if costo[i] <= 0:
            raise ValueError(f"Costo unitario invalido para {i}.")

        if peso[i] < 0 or volumen[i] <= 0:
            raise ValueError(f"Peso o volumen invalido para {i}.")

        if costo_pedido[i] < 0:
            raise ValueError(f"Costo de pedido invalido para {i}.")

    transito_total, transito_zona = calcular_pedidos_en_transito(
        materiales,
        meses,
        demanda,
        inv_inicial,
        zonas_compatibles,
        costo,
        costo_pedido,
        minimo,
        multiplo,
        max_pedidos,
        lead,
        stock_seguridad
    )

    print("\n===== PEDIDOS EN TRANSITO SINTETICOS =====")
    total_transito_valor = 0

    for i in materiales:
        for t in meses:
            q = transito_total.get((i, t), 0)

            if q > 0:
                valor = q * costo[i]
                total_transito_valor += valor

                print(
                    f"{i} | {periodos[t-1]} | "
                    f"{q:,.0f} unidades | ${valor:,.0f}"
                )

    print(
        f"Valor referencial de pedidos en transito: "
        f"${total_transito_valor:,.0f} COP"
    )

    print(
        "Nota: este valor es una estimacion sintetica de compras "
        "previas, no se carga al presupuesto del horizonte."
    )

    # Cotas realistas para evitar BIG-M de millones, que debilitan la
    # relajación del MILP y dificultan que CBC encuentre una solución pronto.
    max_compra_mes = {}
    max_compra_anual = {}
    max_transferencia_material = {}

    for i in materiales:
        limite_presupuesto_mes = presupuesto_mensual / costo[i]
        limite_presupuesto_anual = presupuesto_anual / costo[i]
        peso_zona_compatible = sum(
            numero(filas_zona[z]["capacidad_recepcion_kg_mes"])
            for z in zonas_compatibles[i]
        )
        limite_recepcion = (
            peso_zona_compatible / peso[i]
            if peso[i] > 0 else float("inf")
        )

        max_compra_mes[i] = max(0, int(math.floor(min(
            limite_presupuesto_mes,
            limite_presupuesto_anual,
            limite_recepcion
        ))))
        max_compra_anual[i] = max(0, min(
            int(math.floor(limite_presupuesto_anual)),
            12 * max_compra_mes[i]
        ))
        inventario_sistema = sum(
            inv_inicial[(i, z)] for z in zonas_compatibles[i]
        )
        transito_horizonte = sum(
            transito_total.get((i, t), 0) for t in meses
        )
        max_transferencia_material[i] = (
            inventario_sistema
            + transito_horizonte
            + max_compra_anual[i]
        )

    # ========================================================
    # CREAR MODELO
    # ========================================================

    modelo = pulp.LpProblem("REM_Inventory", pulp.LpMinimize)

    compra_zona = {}
    inventario = {}
    consumo = {}
    faltante = {}
    deficit_ss = {}
    deficit_servicio = {}

    transferencia = {}
    transferencia_activa = {}

    for (zo, zd), parametros_ruta in rutas_transferencia.items():
        materiales_ruta = [
            i for i in materiales
            if zo in zonas_compatibles[i]
            and zd in zonas_compatibles[i]
        ]
        max_transferencia_ruta = sum(
            max_transferencia_material[i] for i in materiales_ruta
        )

        for t in meses:
            transferencia_activa[(zo, zd, t)] = pulp.LpVariable(
                f"YT_{zo}_{zd}_{t}",
                cat="Binary",
                upBound=1 if max_transferencia_ruta > 0 else 0
            )

        for i in materiales_ruta:
            for t in meses:
                transferencia[(i, t, zo, zd)] = pulp.LpVariable(
                    f"T_{nombre_seguro(i)}_{zo}_{zd}_{t}",
                    lowBound=0,
                    upBound=max_transferencia_material[i],
                    cat="Integer"
                )

    pedido_activo = {}
    lotes_pedido = {}

    for i in materiales:
        faltante[i] = {}
        deficit_ss[i] = {}

        for t in meses:
            etiqueta = f"{nombre_seguro(i)}_{t}"

            pedido_activo[(i, t)] = pulp.LpVariable(
                f"Y_{etiqueta}",
                cat="Binary"
            )

            lotes_pedido[(i, t)] = pulp.LpVariable(
                f"K_{etiqueta}",
                lowBound=0,
                upBound=max_compra_mes[i] // multiplo[i],
                cat="Integer"
            )

            faltante[i][t] = pulp.LpVariable(
                f"F_{etiqueta}",
                lowBound=0,
                upBound=demanda.get((i, t), 0),
                cat="Integer"
            )

            deficit_ss[i][t] = pulp.LpVariable(
                f"USS_{etiqueta}",
                lowBound=0,
                upBound=stock_seguridad[i]
            )

            for z in zonas_compatibles[i]:
                etiqueta_z = f"{nombre_seguro(i)}_{z}_{t}"

                compra_zona[(i, t, z)] = pulp.LpVariable(
                    f"QZ_{etiqueta_z}",
                    lowBound=0,
                    upBound=max_compra_mes[i],
                    cat="Integer"
                )

                inventario[(i, t, z)] = pulp.LpVariable(
                    f"I_{etiqueta_z}",
                    lowBound=0,
                    upBound=max(0, int(math.floor(
                        numero(filas_zona[z]["capacidad_m3"]) / volumen[i]
                    ))),
                    cat="Integer"
                )

                consumo[(i, t, z)] = pulp.LpVariable(
                    f"C_{etiqueta_z}",
                    lowBound=0,
                    upBound=demanda.get((i, t), 0),
                    cat="Integer"
                )

        deficit_servicio[i] = pulp.LpVariable(
            f"DS_{nombre_seguro(i)}",
            lowBound=0,
            upBound=sum(demanda.get((i, t), 0) for t in meses)
        )

    # ========================================================
    # FUNCION OBJETIVO
    # ========================================================

    costo_compras_expr = pulp.lpSum(
        costo[i] * compra_zona[(i, t, z)]
        for i in materiales
        for t in meses
        for z in zonas_compatibles[i]
    )

    costo_pedidos_expr = pulp.lpSum(
        costo_pedido[i] * pedido_activo[(i, t)]
        for i in materiales
        for t in meses
    )

    costo_mantener_expr = pulp.lpSum(
        costo[i] * (tasa_mantener_anual / 12)
        * inventario[(i, t, z)]
        for i in materiales
        for t in meses
        for z in zonas_compatibles[i]
    )

    costo_faltantes_expr = pulp.lpSum(
        costo[i] * factor_penalizacion[i] * faltante[i][t]
        for i in materiales
        for t in meses
    )

    costo_deficit_ss_expr = pulp.lpSum(
        costo[i] * 0.10 * deficit_ss[i][t]
        for i in materiales
        for t in meses
    )

    costo_deficit_servicio_expr = pulp.lpSum(
        10 * costo[i] * factor_penalizacion[i] * deficit_servicio[i]
        for i in materiales
    )

    costo_transferencia_fijo_expr = pulp.lpSum(
        rutas_transferencia[(zo, zd)]["costo_fijo"]
        * transferencia_activa[(zo, zd, t)]
        for (zo, zd) in rutas_transferencia
        for t in meses
    )

    costo_transferencia_variable_expr = pulp.lpSum(
        rutas_transferencia[(zo, zd)]["costo_kg"] * peso[i]
        * transferencia[(i, t, zo, zd)]
        for (i, t, zo, zd) in transferencia
    )

    costo_transferencias_expr = (
        costo_transferencia_fijo_expr
        + costo_transferencia_variable_expr
    )

    modelo += (
        costo_compras_expr
        + costo_pedidos_expr
        + costo_mantener_expr
        + costo_faltantes_expr
        + costo_deficit_ss_expr
        + costo_deficit_servicio_expr
        + costo_transferencias_expr
    ), "Costo_total"

    # ========================================================
    # RESTRICCIONES DE TRANSFERENCIA
    # ========================================================

    for (zo, zd) in rutas_transferencia:
        materiales_ruta = [
            i for i in materiales
            if (i, 1, zo, zd) in transferencia
        ]
        max_transferencia_ruta = sum(
            max_transferencia_material[i] for i in materiales_ruta
        )

        for t in meses:
            cantidad_ruta = pulp.lpSum(
                transferencia[(i, t, zo, zd)]
                for i in materiales_ruta
            )

            modelo += (
                cantidad_ruta
                <= max_transferencia_ruta * transferencia_activa[(zo, zd, t)]
            ), f"Activar_transferencia_{zo}_{zd}_{t}"

    # ========================================================
    # RESTRICCIONES DE COMPRAS Y BALANCE
    # ========================================================

    for i in materiales:
        for t in meses:
            zs = zonas_compatibles[i]

            compra_total = pulp.lpSum(
                compra_zona[(i, t, z)] for z in zs
            )

            minimo_real = max(minimo[i], multiplo[i])

            modelo += (
                compra_total == multiplo[i] * lotes_pedido[(i, t)]
            ), f"Multiplo_{nombre_seguro(i)}_{t}"

            modelo += (
                compra_total >= minimo_real * pedido_activo[(i, t)]
            ), f"MOQ_{nombre_seguro(i)}_{t}"

            modelo += (
                compra_total <= max_compra_mes[i] * pedido_activo[(i, t)]
            ), f"Enlace_pedido_{nombre_seguro(i)}_{t}"

            if t + lead[i] > 12:
                modelo += (
                    compra_total == 0
                ), f"Fuera_horizonte_{nombre_seguro(i)}_{t}"

            modelo += (
                pulp.lpSum(consumo[(i, t, z)] for z in zs)
                + faltante[i][t]
                == demanda.get((i, t), 0)
            ), f"Demanda_{nombre_seguro(i)}_{t}"

            for z in zs:
                mes_pedido = t - lead[i]

                llegada_nueva = (
                    compra_zona[(i, mes_pedido, z)]
                    if mes_pedido >= 1 else 0
                )

                llegada_transito = transito_zona.get((i, t, z), 0)

                transferencias_entrada = pulp.lpSum(
                    transferencia[(i, t, zo, z)]
                    for (zo, zd) in rutas_transferencia
                    if zd == z and (i, t, zo, zd) in transferencia
                )

                transferencias_salida = pulp.lpSum(
                    transferencia[(i, t, z, zd)]
                    for (zo, zd) in rutas_transferencia
                    if zo == z and (i, t, z, zd) in transferencia
                )

                inventario_anterior = (
                    inv_inicial[(i, z)]
                    if t == 1
                    else inventario[(i, t - 1, z)]
                )

                modelo += (
                    inventario[(i, t, z)]
                    == inventario_anterior
                    + llegada_nueva
                    + llegada_transito
                    + transferencias_entrada
                    - transferencias_salida
                    - consumo[(i, t, z)]
                ), f"Balance_{nombre_seguro(i)}_{z}_{t}"

            modelo += (
                pulp.lpSum(inventario[(i, t, z)] for z in zs)
                + deficit_ss[i][t]
                >= stock_seguridad[i]
            ), f"Stock_seguridad_{nombre_seguro(i)}_{t}"

        modelo += (
            pulp.lpSum(pedido_activo[(i, t)] for t in meses)
            <= max_pedidos[i]
        ), f"Max_pedidos_{nombre_seguro(i)}"

        primer_mes_evaluable = min(12, lead[i] + 1)

        demanda_evaluable = sum(
            demanda.get((i, t), 0)
            for t in meses
            if t >= primer_mes_evaluable
        )

        faltante_evaluable = pulp.lpSum(
            faltante[i][t]
            for t in meses
            if t >= primer_mes_evaluable
        )

        faltante_permitido = (
            1 - nivel_servicio[i]
        ) * demanda_evaluable

        modelo += (
            faltante_evaluable
            <= faltante_permitido + deficit_servicio[i]
        ), f"Nivel_servicio_{nombre_seguro(i)}"

        modelo += (
            pulp.lpSum(
                inventario[(i, 12, z)] for z in zs
            ) >= stock_seguridad[i]
        ), f"Stock_final_{nombre_seguro(i)}"

    # ========================================================
    # CAPACIDAD DE ALMACENAMIENTO Y RECEPCION
    # ========================================================

    for z in zonas_ids:
        materiales_z = [
            i for i in materiales
            if z in zonas_compatibles[i]
        ]

        capacidad_m3 = numero(filas_zona[z]["capacidad_m3"])
        capacidad_kg = numero(
            filas_zona[z]["capacidad_recepcion_kg_mes"]
        )

        for t in meses:
            modelo += (
                pulp.lpSum(
                    volumen[i] * inventario[(i, t, z)]
                    for i in materiales_z
                ) <= capacidad_m3
            ), f"Volumen_zona_{z}_{t}"

            recepciones = []

            for i in materiales_z:
                mes_pedido = t - lead[i]

                if mes_pedido >= 1:
                    recepciones.append(
                        peso[i] * compra_zona[(i, mes_pedido, z)]
                    )

                recepciones.append(
                    peso[i] * transito_zona.get((i, t, z), 0)
                )

                for (zo, zd) in rutas_transferencia:
                    if zd == z and (i, t, zo, zd) in transferencia:
                        recepciones.append(
                            peso[i] * transferencia[(i, t, zo, zd)]
                        )

            modelo += (
                pulp.lpSum(recepciones) <= capacidad_kg
            ), f"Recepcion_zona_{z}_{t}"

    # ========================================================
    # RESTRICCIONES FINANCIERAS
    # ========================================================

    for t in meses:
        modelo += (
            pulp.lpSum(
                costo[i] * compra_zona[(i, t, z)]
                for i in materiales
                for z in zonas_compatibles[i]
            ) <= presupuesto_mensual
        ), f"Presupuesto_mensual_{t}"

        modelo += (
            pulp.lpSum(
                costo[i] * inventario[(i, t, z)]
                for i in materiales
                for z in zonas_compatibles[i]
            ) <= capital_maximo
        ), f"Capital_inventario_{t}"

    modelo += (
        pulp.lpSum(
            costo[i] * compra_zona[(i, t, z)]
            for i in materiales
            for t in meses
            for z in zonas_compatibles[i]
        ) <= presupuesto_anual
    ), "Presupuesto_anual"

    # ========================================================
    # RESOLVER
    # ========================================================

    print("\nMODELO CONSTRUIDO")
    print("Materiales:", len(materiales))
    print("Periodos:", len(meses))
    print("Zonas:", len(zonas_ids))
    print("Variables:", len(modelo.variables()))
    print("Restricciones:", len(modelo.constraints))

    print("\nFASE 1: BUSCANDO UNA SOLUCIÓN FACTIBLE")
    objetivo_original = modelo.objective
    modelo.setObjective(pulp.LpAffineExpression())
    solver_factibilidad = pulp.PULP_CBC_CMD(
        msg=VER_LOG_SOLVER,
        timeLimit=None
    )
    estado_factibilidad = modelo.solve(solver_factibilidad)
    estado_factibilidad_texto = pulp.LpStatus.get(
        estado_factibilidad, str(estado_factibilidad)
    )

    if modelo.sol_status not in (
        pulp.LpSolutionOptimal,
        pulp.LpSolutionIntegerFeasible
    ):
        raise RuntimeError(
            "CBC no encontró una solución factible en la fase de factibilidad "
            f"(estado: {estado_factibilidad_texto}; solución: {modelo.sol_status}). "
            "Esto suele indicar restricciones incompatibles o datos iniciales que exceden la capacidad."
        )

    valores_factibles = {
        variable.name: variable.varValue
        for variable in modelo.variables()
    }

    print("\nFASE 2: MEJORANDO EL PLAN POR HASTA", TIEMPO_MEJORA_SEGUNDOS, "SEGUNDOS")
    modelo.setObjective(objetivo_original)
    for variable in modelo.variables():
        valor = valores_factibles.get(variable.name)
        if valor is not None:
            variable.setInitialValue(valor)

    try:
        solver_mejora = pulp.PULP_CBC_CMD(
            msg=VER_LOG_SOLVER,
            timeLimit=TIEMPO_MEJORA_SEGUNDOS,
            gapRel=BRECHA_RELATIVA,
            warmStart=True
        )
        estado = modelo.solve(solver_mejora)
        estado_texto = pulp.LpStatus.get(estado, str(estado))
        estado_solucion = modelo.sol_status
    except Exception as error_mejora:
        print("No se pudo mejorar el plan inicial:", error_mejora)
        estado_texto = "FACTIBLE_INICIAL_SIN_MEJORA"
        estado_solucion = None

    if estado_solucion not in (
        pulp.LpSolutionOptimal,
        pulp.LpSolutionIntegerFeasible
    ):
        for variable in modelo.variables():
            variable.varValue = valores_factibles.get(variable.name)
        estado_texto = "FACTIBLE_INICIAL_SIN_MEJORA"
        estado_solucion = pulp.LpSolutionIntegerFeasible

    print("\nESTADO DEL SOLVER:", estado_texto)
    print("ESTADO DE LA SOLUCION:", estado_solucion)

    if estado_solucion == pulp.LpSolutionIntegerFeasible:
        calidad = "FACTIBLE_NO_CERTIFICADA"
        print(
            "El plan es factible, pero no se certificó optimalidad "
            "dentro del tiempo de mejora."
        )
    else:
        calidad = "OPTIMA_DENTRO_TOLERANCIA"

    costo_total = pulp.value(modelo.objective)

    if costo_total is None:
        raise RuntimeError(
            "El solver no devolvio un costo objetivo."
        )

    # ========================================================
    # EXPORTAR RESULTADOS
    # ========================================================

    filas_compras = []
    filas_mensuales = []
    filas_indicadores = []
    filas_transito = []
    filas_transferencias = []
    rutas_fijas_exportadas = set()

    for i in materiales:
        for t in meses:
            total_q = sum(
                int(round(compra_zona[(i, t, z)].value() or 0))
                for z in zonas_compatibles[i]
            )

            if total_q > 0:
                recepcion_mes = t + lead[i]

                periodo_recepcion = (
                    periodos[recepcion_mes - 1]
                    if recepcion_mes <= 12
                    else "FUERA_HORIZONTE"
                )

                for z in zonas_compatibles[i]:
                    qz = int(round(
                        compra_zona[(i, t, z)].value() or 0
                    ))

                    if qz > 0:
                        filas_compras.append({
                            "cod_material": i,
                            "periodo_pedido": periodos[t - 1],
                            "id_zona": z,
                            "id_bodega": filas_zona[z]["id_bodega"],
                            "cantidad_asignada_zona": qz,
                            "cantidad_total_pedido": total_q,
                            "lead_time_meses": lead[i],
                            "periodo_recepcion": periodo_recepcion,
                            "costo_unitario_cop": costo[i],
                            "costo_asignado_cop": qz * costo[i],
                            "estado_solucion": calidad
                        })

            for z in zonas_compatibles[i]:
                filas_mensuales.append({
                    "cod_material": i,
                    "periodo": periodos[t - 1],
                    "id_zona": z,
                    "bodega": filas_zona[z]["id_bodega"],
                    "compra_asignada_zona": int(round(
                        compra_zona[(i, t, z)].value() or 0
                    )),
                    "consumo": int(round(
                        consumo[(i, t, z)].value() or 0
                    )),
                    "transferencias_entrada": int(round(sum(
                        (
                            transferencia[(i, t, zo, z)].value() or 0
                        )
                        for (zo, zd) in rutas_transferencia
                        if zd == z
                        and (i, t, zo, z) in transferencia
                    ))),
                    "transferencias_salida": int(round(sum(
                        (
                            transferencia[(i, t, z, zd)].value() or 0
                        )
                        for (zo, zd) in rutas_transferencia
                        if zo == z
                        and (i, t, z, zd) in transferencia
                    ))),
                    "inventario_final": int(round(
                        inventario[(i, t, z)].value() or 0
                    )),
                    "estado_solucion": calidad
                })

            filas_indicadores.append({
                "cod_material": i,
                "periodo": periodos[t - 1],
                "faltante_material_mes": int(round(
                    faltante[i][t].value() or 0
                )),
                "deficit_stock_seguridad": round(
                    deficit_ss[i][t].value() or 0,
                    4
                ),
                "estado_solucion": calidad
            })

            for (zo, zd) in rutas_transferencia:
                clave_t = (i, t, zo, zd)

                if clave_t in transferencia:
                    cantidad_t = int(round(
                        transferencia[clave_t].value() or 0
                    ))

                    if cantidad_t > 0:
                        kg_t = cantidad_t * peso[i]
                        clave_ruta_mes = (zo, zd, t)
                        costo_fijo_ruta = 0

                        if (
                            clave_ruta_mes not in rutas_fijas_exportadas
                            and (
                                transferencia_activa[
                                    (zo, zd, t)
                                ].value() or 0
                            ) > 0.5
                        ):
                            costo_fijo_ruta = (
                                rutas_transferencia[(zo, zd)]["costo_fijo"]
                            )

                            rutas_fijas_exportadas.add(clave_ruta_mes)

                        filas_transferencias.append({
                            "cod_material": i,
                            "periodo": periodos[t - 1],
                            "id_zona_origen": zo,
                            "id_zona_destino": zd,
                            "cantidad_unidades": cantidad_t,
                            "peso_total_kg": kg_t,
                            "costo_variable_cop": (
                                rutas_transferencia[(zo, zd)]["costo_kg"]
                                * kg_t
                            ),
                            "costo_fijo_ruta_mes_cop": costo_fijo_ruta,
                            "tiempo_translado_dias": (
                                rutas_transferencia[(zo, zd)]["dias"]
                            ),
                            "supuesto_tiempo": (
                                "MISMO_MES_POR_HORIZONTE_MENSUAL"
                            )
                        })

            q_transito = transito_total.get((i, t), 0)

            if q_transito > 0:
                filas_transito.append({
                    "cod_material": i,
                    "periodo_recepcion": periodos[t - 1],
                    "cantidad_transito_total": q_transito,
                    "valor_estimado_pagado_previamente_cop": (
                        q_transito * costo[i]
                    ),
                    "origen": "SIMULACION_POLITICA_EOQ"
                })

    compras_df = pd.DataFrame(filas_compras)
    mensuales_df = pd.DataFrame(filas_mensuales)
    indicadores_df = pd.DataFrame(filas_indicadores)
    transito_df = pd.DataFrame(filas_transito)
    transferencias_resultado_df = pd.DataFrame(filas_transferencias)

    ruta_compras = (
        CARPETA_RESULTADOS / "compras_optimizadas.csv"
    )

    ruta_mensuales = (
        CARPETA_RESULTADOS / "resultados_mensuales_optimizados.csv"
    )

    ruta_indicadores = (
        CARPETA_RESULTADOS / "indicadores_material_mes_optimizados.csv"
    )

    ruta_transito = (
        CARPETA_RESULTADOS / "pedidos_transito_sinteticos.csv"
    )

    ruta_transferencias = (
        CARPETA_RESULTADOS / "transferencias_optimizadas.csv"
    )

    compras_df.to_csv(
        ruta_compras,
        index=False,
        encoding="utf-8-sig"
    )

    mensuales_df.to_csv(
        ruta_mensuales,
        index=False,
        encoding="utf-8-sig"
    )

    indicadores_df.to_csv(
        ruta_indicadores,
        index=False,
        encoding="utf-8-sig"
    )

    transito_df.to_csv(
        ruta_transito,
        index=False,
        encoding="utf-8-sig"
    )

    transferencias_resultado_df.to_csv(
        ruta_transferencias,
        index=False,
        encoding="utf-8-sig"
    )

    # ========================================================
    # RESUMEN DE COSTOS Y SERVICIO
    # ========================================================

    costo_compras = pulp.value(costo_compras_expr) or 0
    costo_pedidos = pulp.value(costo_pedidos_expr) or 0
    costo_mantener = pulp.value(costo_mantener_expr) or 0
    costo_faltantes = pulp.value(costo_faltantes_expr) or 0
    costo_deficit_ss = pulp.value(costo_deficit_ss_expr) or 0

    costo_deficit_servicio = (
        pulp.value(costo_deficit_servicio_expr) or 0
    )

    costo_transferencias = (
        pulp.value(costo_transferencias_expr) or 0
    )

    costo_transferencias_fijo = (
        pulp.value(costo_transferencia_fijo_expr) or 0
    )

    costo_transferencias_variable = (
        pulp.value(costo_transferencia_variable_expr) or 0
    )

    demanda_total = sum(demanda.values())

    faltantes_totales = sum(
        int(round(faltante[i][t].value() or 0))
        for i in materiales
        for t in meses
    )

    nivel_servicio_logrado = (
        1 - faltantes_totales / demanda_total
        if demanda_total > 0 else 1
    )

    print("\n===== RESULTADOS DEL MODELO =====")
    print("Calidad:", calidad)
    print(f"Costo total: ${costo_total:,.2f} COP")
    print(f"Compras: ${costo_compras:,.2f} COP")
    print(f"Pedidos: ${costo_pedidos:,.2f} COP")
    print(f"Mantenimiento: ${costo_mantener:,.2f} COP")
    print(
        f"Penalizacion faltantes: ${costo_faltantes:,.2f} COP"
    )
    print(
        f"Penalizacion deficit SS: ${costo_deficit_ss:,.2f} COP"
    )
    print(
        f"Penalizacion deficit servicio: "
        f"${costo_deficit_servicio:,.2f} COP"
    )
    print(
        f"Transferencias: ${costo_transferencias:,.2f} COP"
    )
    print(
        f"  Costos fijos: "
        f"${costo_transferencias_fijo:,.2f} COP"
    )
    print(
        f"  Costos por kg: "
        f"${costo_transferencias_variable:,.2f} COP"
    )
    print(f"Unidades faltantes: {faltantes_totales:,.0f}")
    print(
        f"Nivel de servicio global: {nivel_servicio_logrado:.2%}"
    )

    print("\nArchivos generados:")
    print(ruta_compras)
    print(ruta_mensuales)
    print(ruta_indicadores)
    print(ruta_transito)
    print(ruta_transferencias)

    print("\nEl inventario REAL de MySQL no fue modificado.")

    return {
        "calidad": calidad,
        "estado_solver": estado_texto,
        "costo_total": costo_total,
        "nivel_servicio": nivel_servicio_logrado,
        "faltantes": faltantes_totales,
        "costo_transferencias": costo_transferencias,
        "compras": compras_df,
        "transferencias": transferencias_resultado_df,
        "resultados_mensuales": mensuales_df,
        "indicadores_material_mes": indicadores_df,
        "pedidos_transito": transito_df
    }


# ============================================================
# EJECUCION DIRECTA
# ============================================================

if __name__ == "__main__":
    try:
        resolver_optimizacion()
    except Exception as error:
        print("\nERROR EN LA OPTIMIZACION:", error)
        raise
