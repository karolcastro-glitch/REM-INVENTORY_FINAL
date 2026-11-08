import os
import numpy as np                 # cálculos matemáticos (raíces, redondeos)
import pandas as pd                # lectura y tratamiento de tablas
import pulp                        # formulación y solución del MILP (solver CBC)
import matplotlib
import matplotlib.pyplot as plt    # gráficos

# Carpeta donde están los archivos de entrada y donde se guardan los resultados
from pathlib import Path

# Directorio principal del proyecto REM_INVENTORY
PROYECTO = Path(__file__).resolve().parents[2]

# Carpetas de entrada y salida
RUTA_ENTRADA = PROYECTO / "data"
RUTA_SALIDA = Path(__file__).resolve().parent / "resultados"

# Archivos originales
ARCHIVO_BASES = RUTA_ENTRADA / "Etapa2_Bases_sinteticas_inventarios.xlsx"
ARCHIVO_ABC = RUTA_ENTRADA / "Etapa1_Matriz_ABC_multicriterio_SINTETICO.xlsx"

print("Carpeta del proyecto:", PROYECTO)
print("Archivo de bases existe:", ARCHIVO_BASES.exists())
print("Archivo ABC existe:", ARCHIVO_ABC.exists())

if not ARCHIVO_BASES.exists() or not ARCHIVO_ABC.exists():
    raise FileNotFoundError("No se encontraron los archivos Excel en la carpeta data.")

# %% ==========================================================================
# SECCIÓN 2. CARGA DE INFORMACIÓN
# Cada hoja del Excel se carga en una tabla (DataFrame). La llave común es cod_material.
# =============================================================================
hojas = pd.read_excel(ARCHIVO_BASES, sheet_name=None)
maestro     = hojas["02_maestro"]
dem_hist    = hojas["03_demanda_historica"]
proveedores = hojas["04_proveedores"]
inventarios = hojas["05_inventarios"]
financiero  = hojas["06_restricciones_financieras"]
almacen     = hojas["07_capacidad_almacen"]
servicio    = hojas["08_parametros_servicio"]
dem_hor     = hojas["09_demanda_horizonte"]
escenarios  = hojas["10_escenarios"]

seleccion = pd.read_excel(ARCHIVO_ABC, sheet_name="Seleccion_final")
print("Hojas cargadas:", list(hojas.keys()))

# %% ==========================================================================
# SECCIÓN 3. VALIDACIÓN Y PREPARACIÓN DE DATOS
# Antes de optimizar se verifica que las tablas sean consistentes entre sí.
# =============================================================================
MATERIALES = maestro["cod_material"].tolist()

# 3.1 Todas las tablas deben contener exactamente los mismos materiales
for nombre, tabla in [("proveedores", proveedores), ("inventarios", inventarios),
                      ("demanda horizonte", dem_hor), ("demanda histórica", dem_hist)]:
    faltan = set(MATERIALES) - set(tabla["cod_material"])
    assert not faltan, f"En {nombre} faltan materiales: {faltan}"

# 3.2 No se aceptan cantidades ni costos negativos
assert (dem_hist["cantidad"] >= 0).all() and (dem_hor["demanda_pronosticada"] >= 0).all()
assert (maestro["costo_unitario_cop"] > 0).all()

# 3.3 Inventario disponible = inicial - comprometido
assert (inventarios["inventario_disponible"] ==
        inventarios["inventario_inicial"] - inventarios["inventario_comprometido"]).all()

# 3.4 Matriz de demanda del horizonte: filas = material, columnas = mes 1..12
PERIODOS = sorted(dem_hor["periodo"].unique())          # '2026-10' ... '2027-09'
T = list(range(1, len(PERIODOS) + 1))                   # 1..12
D_base = (dem_hor.pivot(index="cod_material", columns="periodo", values="demanda_pronosticada")
          .loc[MATERIALES, PERIODOS])
D_base.columns = T

# 3.5 Estadísticos de la demanda histórica mensual (insumo del inventario de seguridad)
hist_mes = (dem_hist.groupby(["cod_material", "periodo"])["cantidad"].sum()
            .unstack(fill_value=0).loc[MATERIALES])
d_mes  = hist_mes.iloc[:, -12:].mean(axis=1)    # promedio de los últimos 12 meses
sd_mes = hist_mes.std(axis=1)                   # desviación mensual de los 36 meses

# 3.6 Tabla única por material (une maestro + proveedores + inventarios + servicio)
base = (maestro.merge(proveedores.drop(columns=["costo_adquisicion_cop"]), on="cod_material")
               .merge(inventarios, on="cod_material")
               .merge(servicio, on="criticidad")
               .set_index("cod_material").loc[MATERIALES])

# 3.7 Parámetros globales (vienen de la hoja 06 y 07)
fin = financiero.set_index("parametro")["valor"]
TASA_MANTENER = float(fin["tasa_costo_mantener_anual"])
PRESUPUESTO_MES = float(fin["presupuesto_compras_mensual_cop"])
LIMITE_INVERSION = float(fin["limite_inversion_inventario_cop"])
alm = almacen.set_index("zona_almacen")
print(f"{len(MATERIALES)} materiales, {len(T)} meses: {PERIODOS[0]} a {PERIODOS[-1]}")

# %% ==========================================================================
# SECCIÓN 4. CLASIFICACIÓN ABC MULTICRITERIO (resultado de la Etapa 1)
# La clasificación se hizo en la Etapa 1; aquí solo se trae para trazabilidad.
# =============================================================================
print(seleccion[["rango", "cod_material", "clase_abc", "puntaje", "C2_criticidad"]].to_string(index=False))

# %% ==========================================================================
# SECCIÓN 5. SELECCIÓN DE MATERIALES
# Se verifica que los materiales del modelo sean exactamente los 12 seleccionados.
# =============================================================================
assert set(seleccion["cod_material"]) == set(MATERIALES), "La selección ABC no coincide con el maestro"
print("OK: los 12 materiales del modelo coinciden con la selección ABC.")

# %% ==========================================================================
# SECCIÓN 6. CÁLCULO DEL EOQ TRADICIONAL (referencia sin restricciones)
# EOQ = raíz(2·D·S / H)   donde H = tasa de mantener × costo unitario
# =============================================================================
def calcular_eoq(D_mensual, b):
    e = pd.DataFrame(index=MATERIALES)
    e["D_anual"] = D_mensual.sum(axis=1)
    e["S"] = b["costo_pedido_cop"]
    e["H"] = TASA_MANTENER * b["costo_unitario_cop"]
    e["EOQ"] = np.sqrt(2 * e["D_anual"] * e["S"] / e["H"])
    e["N_pedidos"] = e["D_anual"] / e["EOQ"]
    e["dias_entre_pedidos"] = 365 / e["N_pedidos"]
    e["CTR"] = e["N_pedidos"] * e["S"] + e["EOQ"] / 2 * e["H"]
    # EOQ "práctico": respeta pedido mínimo, múltiplo y frecuencia máxima del proveedor
    q = np.maximum.reduce([e["EOQ"], b["cantidad_minima_pedido"], e["D_anual"] / b["max_pedidos_anio"]])
    e["Q_ajustado"] = np.ceil(q / b["multiplo_compra"]) * b["multiplo_compra"]
    e["N_ajustado"] = e["D_anual"] / e["Q_ajustado"]
    e["CTR_ajustado"] = e["N_ajustado"] * e["S"] + e["Q_ajustado"] / 2 * e["H"]
    return e

eoq = calcular_eoq(D_base, base)
print(eoq[["D_anual", "EOQ", "N_pedidos", "Q_ajustado", "CTR", "CTR_ajustado"]].round(1))

# %% ==========================================================================
# SECCIÓN 7. DEFINICIÓN DE PARÁMETROS
# Toda la información del modelo se arma en un diccionario a partir de las bases.
# Se construye con una función para poder reutilizarla en los escenarios.
# =============================================================================
# Nivel de servicio "exigente" (escenario E6): sube un escalón por criticidad
SERVICIO_EXIGENTE = {0.98: (0.995, 2.576), 0.95: (0.98, 2.054), 0.90: (0.95, 1.645)}
MULTIPLO_SS = {"CON-ACSR2": 10, "CON-ACSR1/0": 10}   # SS de conductores en decenas de metros


def calcular_ss(z, d, sd, L_meses, sL_meses, materiales):
    """Inventario de seguridad: SS = z·√(L·σd² + d²·σL²), redondeado hacia arriba."""
    ss = np.ceil(z * np.sqrt(L_meses * sd**2 + d**2 * sL_meses**2))
    for m, r in MULTIPLO_SS.items():
        if m in materiales:
            ss[m] = np.ceil(ss[m] / r) * r
    return ss


def pedidos_en_transito(b, D, ss, Qprev, L):
    """
    Pedidos hechos ANTES del horizonte (política previa tipo EOQ) que llegan en los
    meses 1..L. Sin ellos, los primeros L meses tendrían faltantes que el modelo no
    puede evitar, porque ninguna compra suya alcanza a llegar a tiempo.
    Regla: si el inventario proyectado cae por debajo del SS, llega un lote Q_ajustado
    (o más, si hace falta), en múltiplos de compra.
    """
    R = pd.DataFrame(0.0, index=MATERIALES, columns=T)
    for i in MATERIALES:
        inv = b.loc[i, "inventario_disponible"]
        for t in range(1, int(L[i]) + 1):
            if inv - D.loc[i, t] < ss[i]:
                falta = ss[i] - (inv - D.loc[i, t])
                lote = max(Qprev[i], falta)
                lote = np.ceil(lote / b.loc[i, "multiplo_compra"]) * b.loc[i, "multiplo_compra"]
                R.loc[i, t] = lote
                inv += lote
            inv -= D.loc[i, t]
    return R


def construir_parametros(esc):
    """Arma todos los parámetros del modelo para un escenario (fila de la hoja 10)."""
    b = base.copy()
    P = {}
    # --- Demanda (multiplicador de demanda) ---
    P["D"] = D_base * esc["mult_demanda"]
    # --- Costos ---
    P["c"] = b["costo_unitario_cop"] * esc["mult_costo"]                 # COP/um
    P["S"] = b["costo_pedido_cop"]                                       # COP/pedido
    P["h"] = TASA_MANTENER / 12 * P["c"]                                 # COP/um-mes
    P["p"] = b["factor_penalizacion_faltante"] * P["c"]                  # COP/um faltante
    P["q"] = 0.10 * P["c"]                                               # COP/um-mes bajo SS
    # --- Tiempo de reposición (en meses enteros, redondeo hacia arriba) ---
    dias = b["tiempo_reposicion_dias"] * esc["mult_tiempo_reposicion"]
    P["L"] = np.ceil(dias / 30).astype(int)
    # --- Nivel de servicio y SS (recalculado con la fórmula estocástica) ---
    beta, z = b["nivel_servicio"].copy(), b["z"].copy()
    if esc["subir_nivel_servicio"] == 1:
        beta = b["nivel_servicio"].map(lambda v: SERVICIO_EXIGENTE[round(v, 2)][0])
        z = b["nivel_servicio"].map(lambda v: SERVICIO_EXIGENTE[round(v, 2)][1])
    P["beta"] = beta
    P["SS"] = calcular_ss(z, d_mes * esc["mult_demanda"], sd_mes * esc["mult_demanda"],
                          dias / 30, b["desv_tiempo_reposicion_dias"] * esc["mult_tiempo_reposicion"] / 30,
                          MATERIALES)
    # --- Reglas del proveedor ---
    P["MOQ"], P["m"], P["Nmax"] = b["cantidad_minima_pedido"], b["multiplo_compra"], b["max_pedidos_anio"]
    # --- Inventario inicial y capacidades ---
    P["I0"] = b["inventario_disponible"]
    P["Cap"] = np.floor(b["capacidad_almacen_material"] * esc["mult_capacidad"])
    P["v"], P["w"], P["zona"] = b["volumen_m3_ud"], b["peso_kg_ud"], b["zona_almacen"]
    P["V"] = alm["capacidad_m3"] * esc["mult_capacidad"]
    P["W"] = alm["capacidad_recepcion_kg_mes"]
    # --- Financieros ---
    P["B"] = PRESUPUESTO_MES * esc["mult_presupuesto"]
    P["INVmax"] = LIMITE_INVERSION
    # --- Pedidos en tránsito (política previa basada en EOQ) ---
    Qprev = calcular_eoq(P["D"], b)["Q_ajustado"]
    P["R"] = pedidos_en_transito(b, P["D"], P["SS"], Qprev, P["L"])
    return P


VERBOSE = bool(int(os.environ.get("VERBOSE", "0")))
ESC_BASE = escenarios.set_index("escenario").loc["E0"]
P = construir_parametros(ESC_BASE)

# Control: el SS recalculado debe coincidir con el de la hoja 05
assert (P["SS"] == base["inventario_seguridad"]).all(), "SS recalculado ≠ SS de la base"
print("OK: SS recalculado = hoja 05.\nPedidos en tránsito (llegadas por mes):")
print(P["R"].loc[(P["R"] > 0).any(axis=1)])

# %% ==========================================================================
# SECCIONES 8 a 11. VARIABLES, FUNCIÓN OBJETIVO, RESTRICCIONES Y SOLUCIÓN
# Todo el modelo queda dentro de una función para reutilizarlo en los escenarios.
# =============================================================================
GAP = 0.001   # brecha de optimalidad aceptada (0,1 %)


def resolver_modelo(P, nombre="E0", tiempo_max=120, verbose=False):
    I, Tm = MATERIALES, T
    D, L = P["D"], P["L"]
    mdl = pulp.LpProblem(f"Inventarios_{nombre}", pulp.LpMinimize)

    # ---------- SECCIÓN 8. VARIABLES DE DECISIÓN ----------
    idx = [(i, t) for i in I for t in Tm]
    Q = pulp.LpVariable.dicts("Q", idx, lowBound=0)                    # cantidad pedida (um)
    k = pulp.LpVariable.dicts("k", idx, lowBound=0, cat="Integer")     # número de lotes
    y = pulp.LpVariable.dicts("y", idx, cat="Binary")                  # 1 si se pide
    Inv = pulp.LpVariable.dicts("I", idx, lowBound=0)                  # inventario final (um)
    F = pulp.LpVariable.dicts("F", idx, lowBound=0)                    # faltante (um)
    U = pulp.LpVariable.dicts("U", idx, lowBound=0)                    # déficit frente al SS (um)

    def llegada(i, t):
        """Lo que llega en t = lo pedido por el modelo en t-L + lo que ya venía en tránsito."""
        origen = t - L[i]
        return (Q[(i, origen)] if origen >= 1 else 0) + P["R"].loc[i, t]

    def M_big(i, t):
        resto = float(D.loc[i, [s for s in Tm if s >= t + L[i]]].sum()) + P["SS"][i]
        resto = max(P["MOQ"][i], np.ceil(resto / P["m"][i]) * P["m"][i])
        tope_ppto = np.floor(P["B"] / P["c"][i] / P["m"][i]) * P["m"][i]
        return float(min(P["Cap"][i], resto, tope_ppto))

    # ---------- SECCIÓN 9. FUNCIÓN OBJETIVO ----------
    mdl += (
        pulp.lpSum(P["c"][i] * Q[(i, t)] for i, t in idx)        # (1) adquisición
        + pulp.lpSum(P["S"][i] * y[(i, t)] for i, t in idx)      # (2) ordenar
        + pulp.lpSum(P["h"][i] * Inv[(i, t)] for i, t in idx)    # (3) mantener
        + pulp.lpSum(P["q"][i] * U[(i, t)] for i, t in idx)      # (4) déficit de SS
        + pulp.lpSum(P["p"][i] * F[(i, t)] for i, t in idx)      # (5) faltantes
    ), "Costo_total"

    # ---------- SECCIÓN 10. RESTRICCIONES ----------
    for i in I:
        for t in Tm:
            previo = P["I0"][i] if t == 1 else Inv[(i, t - 1)]
            # R1. Balance de inventario con tiempo de reposición
            mdl += Inv[(i, t)] == previo + llegada(i, t) - D.loc[i, t] + F[(i, t)], f"R1_{i}_{t}"
            # R2. Inventario de seguridad como meta blanda
            mdl += Inv[(i, t)] + U[(i, t)] >= P["SS"][i], f"R2_{i}_{t}"
            # R5. Compras en múltiplos del lote del proveedor
            mdl += Q[(i, t)] == P["m"][i] * k[(i, t)], f"R5_{i}_{t}"
            # R6. Pedido mínimo y vínculo con la binaria
            #     M ajustado = lo máximo que tiene sentido pedir: no más que la capacidad del
            #     material, ni que el presupuesto del mes, ni que toda la demanda restante + SS
            #     (redondeada al múltiplo). Un M "apretado" acelera mucho al solver.
            mdl += Q[(i, t)] >= P["MOQ"][i] * y[(i, t)], f"R6a_{i}_{t}"
            mdl += Q[(i, t)] <= M_big(i, t) * y[(i, t)], f"R6b_{i}_{t}"
            # R8. Un pedido que llega después del mes 12 no se permite
            if t + L[i] > Tm[-1]:
                mdl += y[(i, t)] == 0, f"R8_{i}_{t}"
            # R9. Espacio asignado al material
            mdl += Inv[(i, t)] <= P["Cap"][i], f"R9_{i}_{t}"
        # R3. Nivel de servicio (solo desde que el modelo controla las llegadas: t > L)
        meses_ctrl = [t for t in Tm if t > L[i]]
        if meses_ctrl:
            mdl += (pulp.lpSum(F[(i, t)] for t in meses_ctrl)
                    <= (1 - P["beta"][i]) * float(D.loc[i, meses_ctrl].sum())), f"R3_{i}"
        # R4. Cerrar el horizonte con al menos el SS
        mdl += Inv[(i, Tm[-1])] >= P["SS"][i], f"R4_{i}"
        # R7. Frecuencia máxima de pedidos en el año
        mdl += pulp.lpSum(y[(i, t)] for t in Tm) <= P["Nmax"][i], f"R7_{i}"

    for t in Tm:
        for zna in P["V"].index:
            Iz = [i for i in I if P["zona"][i] == zna]
            # R10. Volumen ocupado por zona (bodega cubierta / patio)
            mdl += pulp.lpSum(P["v"][i] * Inv[(i, t)] for i in Iz) <= P["V"][zna], f"R10_{zna}_{t}"
            # R11. Capacidad de recepción (kg que llegan en el mes)
            mdl += pulp.lpSum(P["w"][i] * llegada(i, t) for i in Iz) <= P["W"][zna], f"R11_{zna}_{t}"
        # R12. Presupuesto de compras del mes (se compromete al emitir el pedido)
        mdl += pulp.lpSum(P["c"][i] * Q[(i, t)] for i in I) <= P["B"], f"R12_{t}"
        # R13. Valor máximo del inventario en bodega
        mdl += pulp.lpSum(P["c"][i] * Inv[(i, t)] for i in I) <= P["INVmax"], f"R13_{t}"

    # ---------- SECCIÓN 11. EJECUCIÓN DEL OPTIMIZADOR ----------
    # Se usa HiGHS si está instalado (más rápido en modelos de dimensionamiento de lotes);
    # si no, CBC, que viene incluido con PuLP. Ambos son gratuitos.
    if "HiGHS" in pulp.listSolvers(onlyAvailable=True):
        solver = pulp.HiGHS(msg=verbose, timeLimit=tiempo_max, gapRel=GAP)
    else:
        solver = pulp.PULP_CBC_CMD(msg=verbose, timeLimit=tiempo_max, gapRel=GAP)
    mdl.solve(solver)
    estado = pulp.LpStatus[mdl.status]
    if mdl.sol_status == pulp.LpSolutionIntegerFeasible:
        estado = "Factible – detenido por límite de tiempo (ver brecha en el log del solver)"

    # ---------- SECCIÓN 12. EXTRACCIÓN DE RESULTADOS ----------
    tabla = lambda var: pd.DataFrame({t: {i: (var[(i, t)].value() or 0.0) for i in I} for t in Tm})
    res = {"estado": estado, "objetivo": pulp.value(mdl.objective), "modelo": mdl,
           "Q": tabla(Q).round(4), "y": tabla(y).round(0), "I": tabla(Inv).round(4),
           "F": tabla(F).round(4), "U": tabla(U).round(4)}
    res["Llegadas"] = pd.DataFrame({t: {i: (res["Q"].loc[i, t - L[i]] if t - L[i] >= 1 else 0)
                                        + P["R"].loc[i, t] for i in I} for t in Tm})
    return res


res = resolver_modelo(P, "E0", verbose=VERBOSE)
print("Estado:", res["estado"], "| Costo total (objetivo): {:,.0f} COP".format(res["objetivo"]))
n_var = len(res["modelo"].variables()); n_res = len(res["modelo"].constraints)
print(f"Tamaño: {n_var} variables, {n_res} restricciones")

# %% ==========================================================================
# SECCIÓN 13. VALIDACIÓN DE LA SOLUCIÓN
# Se recalcula todo "a mano" con los valores obtenidos para verificar que la
# solución cumple cada restricción (tolerancia numérica pequeña).
# =============================================================================
def validar(P, res, tol=1e-4):
    Q, Inv, F, Lleg, y = res["Q"], res["I"], res["F"], res["Llegadas"], res["y"]
    chk = []
    prev = Inv.shift(1, axis=1); prev[1] = P["I0"]
    bal = (Inv - (prev + Lleg - P["D"] + F)).abs().max().max()
    chk.append(("R1 Balance de inventario", bal <= tol, f"máx. desviación {bal:.2e}"))
    mult = ((Q / P["m"].values[:, None]) - np.round(Q / P["m"].values[:, None])).abs().max().max()
    chk.append(("R5 Múltiplos de compra", mult <= tol, f"máx. residuo {mult:.2e}"))
    moq = ((Q > tol) & (Q.lt(P["MOQ"], axis=0))).sum().sum()
    chk.append(("R6 Pedido mínimo", moq == 0, f"{moq} incumplimientos"))
    frec = (y.sum(axis=1) > P["Nmax"]).sum()
    chk.append(("R7 Frecuencia máxima", frec == 0, f"{frec} incumplimientos"))
    fin = (Inv[T[-1]] < P["SS"] - tol).sum()
    chk.append(("R4 Inventario final ≥ SS", fin == 0, f"{fin} incumplimientos"))
    for zna in P["V"].index:
        vol = (Inv.mul(P["v"], axis=0)[P["zona"] == zna]).sum().max()
        chk.append((f"R10 Volumen {zna}", vol <= P["V"][zna] + tol, f"máx. {vol:.1f} de {P['V'][zna]:.0f} m³"))
    gasto = Q.mul(P["c"], axis=0).sum().max()
    chk.append(("R12 Presupuesto mensual", gasto <= P["B"] + 1, f"máx. {gasto/1e6:,.0f} de {P['B']/1e6:,.0f} M COP"))
    valor = Inv.mul(P["c"], axis=0).sum().max()
    chk.append(("R13 Límite de inversión", valor <= P["INVmax"] + 1, f"máx. {valor/1e9:.2f} de {P['INVmax']/1e9:.2f} mil M"))
    for i in MATERIALES:
        mc = [t for t in T if t > P["L"][i]]
        if mc:
            ok = F.loc[i, mc].sum() <= (1 - P["beta"][i]) * P["D"].loc[i, mc].sum() + tol
            if not ok:
                chk.append((f"R3 Nivel de servicio {i}", False, "incumple"))
    chk.append(("R3 Nivel de servicio (12 materiales)", all(c[1] for c in chk if c[0].startswith("R3 N")), "revisado"))
    return pd.DataFrame(chk, columns=["restriccion", "cumple", "detalle"])

validacion = validar(P, res)
print(validacion.to_string(index=False))

# %% ==========================================================================
# SECCIÓN 14. INDICADORES Y COMPARACIÓN EOQ vs. MODELO OPTIMIZADO
# =============================================================================
def indicadores(P, res):
    Q, Inv, F, U, y = res["Q"], res["I"], res["F"], res["U"], res["y"]
    k = pd.DataFrame(index=MATERIALES)
    k["compra_total_um"] = Q.sum(axis=1)
    k["n_pedidos"] = y.sum(axis=1).astype(int)
    k["lote_promedio"] = (k["compra_total_um"] / k["n_pedidos"].replace(0, np.nan)).round(1)
    k["meses_pedido"] = y.apply(lambda r: ", ".join(PERIODOS[t - 1] for t in T if r[t] > 0.5), axis=1)
    k["inventario_promedio"] = Inv.mean(axis=1).round(1)
    k["SS"] = P["SS"]
    k["inventario_min"] = Inv.min(axis=1).round(1)
    k["meses_bajo_SS"] = (U > 1e-6).sum(axis=1)
    k["faltante_total"] = F.sum(axis=1).round(1)
    k["nivel_servicio_logrado_%"] = (100 * (1 - F.sum(axis=1) / P["D"].sum(axis=1))).round(2)
    k["cobertura_min_meses"] = (Inv.min(axis=1) / P["D"].mean(axis=1)).round(2)
    k["inversion_compras_cop"] = Q.mul(P["c"], axis=0).sum(axis=1)
    k["costo_ordenar"] = k["n_pedidos"] * P["S"]
    k["costo_mantener"] = Inv.mul(P["h"], axis=0).sum(axis=1)
    k["costo_deficit_SS"] = U.mul(P["q"], axis=0).sum(axis=1)
    k["costo_faltantes"] = F.mul(P["p"], axis=0).sum(axis=1)
    # Nivel de riesgo: combina faltantes, meses bajo SS y cobertura mínima
    k["riesgo_desabastecimiento"] = np.select(
        [k["faltante_total"] > 0, k["meses_bajo_SS"] >= 3, k["cobertura_min_meses"] < 1.5],
        ["ALTO", "MEDIO", "MEDIO"], "BAJO")
    return k

kpi = indicadores(P, res)

# Indicadores globales (responden preguntas gerenciales)
gasto_mes = res["Q"].mul(P["c"], axis=0).sum()
vol_mes = {z: res["I"].mul(P["v"], axis=0)[P["zona"] == z].sum() for z in P["V"].index}
costos = {
    "Adquisición": kpi["inversion_compras_cop"].sum(), "Ordenar": kpi["costo_ordenar"].sum(),
    "Mantener": kpi["costo_mantener"].sum(), "Déficit de SS": kpi["costo_deficit_SS"].sum(),
    "Faltantes": kpi["costo_faltantes"].sum()}
resumen = pd.DataFrame({
    "indicador": ["Costo total de la política (COP)", "Costo relevante = ordenar + mantener (COP)",
                  "Compras del horizonte (COP)", "% presupuesto anual utilizado",
                  "Mes de mayor uso del presupuesto (%)", "% ocupación máx. bodega cubierta",
                  "% ocupación máx. patio", "Valor máx. inventario (COP)", "Pedidos emitidos",
                  "Unidades faltantes (todas)"],
    "valor": [sum(costos.values()), costos["Ordenar"] + costos["Mantener"], costos["Adquisición"],
              round(100 * gasto_mes.sum() / (P["B"] * 12), 1), round(100 * gasto_mes.max() / P["B"], 1),
              round(100 * vol_mes["CUBIERTA"].max() / P["V"]["CUBIERTA"], 1),
              round(100 * vol_mes["PATIO"].max() / P["V"]["PATIO"], 1),
              res["I"].mul(P["c"], axis=0).sum().max(), int(kpi["n_pedidos"].sum()),
              round(kpi["faltante_total"].sum(), 1)]})
print(resumen.to_string(index=False))

# Comparación EOQ vs. MILP
# Nota: el EOQ es una política "promedio" de un año; el MILP decide mes a mes con
# inventario inicial, pedidos en tránsito y restricciones. Se comparan tamaños de lote,
# número de pedidos y costos relevantes (ordenar + mantener, incluido el SS).
comp = pd.DataFrame(index=MATERIALES)
comp["EOQ_lote"] = eoq["EOQ"].round(1)
comp["EOQ_ajustado_lote"] = eoq["Q_ajustado"]
comp["MILP_lote_prom"] = kpi["lote_promedio"]
comp["EOQ_pedidos_anio"] = eoq["N_pedidos"].round(1)
comp["MILP_pedidos"] = kpi["n_pedidos"]
comp["EOQ_inv_prom"] = (eoq["EOQ"] / 2 + P["SS"]).round(1)
comp["MILP_inv_prom"] = kpi["inventario_promedio"]
comp["EOQ_costo_relevante"] = (eoq["CTR"] + P["SS"] * eoq["H"]).round(0)
comp["MILP_costo_relevante"] = (kpi["costo_ordenar"] + kpi["costo_mantener"]).round(0)
comp["dif_lote_%"] = (100 * (comp["MILP_lote_prom"] / comp["EOQ_lote"] - 1)).round(1)
print(comp.to_string())

# %% ==========================================================================
# SECCIÓN 15. VISUALIZACIÓN Y EXPORTACIÓN DE RESULTADOS
# =============================================================================
os.makedirs(RUTA_SALIDA, exist_ok=True)
etq = [p[2:] for p in PERIODOS]   # '26-10' ...

# Gráfico 1: inventario vs. SS y llegadas para 4 materiales representativos
fig, ax = plt.subplots(2, 2, figsize=(13, 8))
for a, i in zip(ax.flat, ["TR-015", "REC-15", "POS-12C", "MED-MONO"]):
    a.bar(etq, res["Llegadas"].loc[i], color="#9ecae1", label="Llegadas")
    a.plot(etq, res["I"].loc[i], marker="o", color="#08519c", label="Inventario final")
    a.axhline(P["SS"][i], color="red", ls="--", label=f"SS = {P['SS'][i]:.0f}")
    a.set_title(f"{i} (tiempo reposición {P['L'][i]} meses)"); a.tick_params(axis="x", rotation=45)
ax[0, 0].legend(fontsize=8); fig.suptitle("Inventario vs. inventario de seguridad – escenario base (sintético)")
fig.tight_layout(); fig.savefig(os.path.join(RUTA_SALIDA, "g1_inventario_vs_SS.png"), dpi=130)

# Gráfico 2: uso del presupuesto mensual
fig, ax = plt.subplots(figsize=(11, 4))
ax.bar(etq, gasto_mes / 1e6, color="#3182bd"); ax.axhline(P["B"] / 1e6, color="red", ls="--", label="Presupuesto")
ax.set_ylabel("Millones COP"); ax.set_title("Compras comprometidas por mes vs. presupuesto"); ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(RUTA_SALIDA, "g2_presupuesto.png"), dpi=130)

# Gráfico 3: ocupación de almacenamiento por zona
fig, ax = plt.subplots(figsize=(11, 4))
for zna, col in [("CUBIERTA", "#31a354"), ("PATIO", "#fd8d3c")]:
    ax.plot(etq, 100 * vol_mes[zna] / P["V"][zna], marker="o", color=col, label=zna)
ax.axhline(100, color="red", ls="--"); ax.set_ylabel("% de capacidad"); ax.legend()
ax.set_title("Ocupación de almacenamiento por zona")
fig.tight_layout(); fig.savefig(os.path.join(RUTA_SALIDA, "g3_ocupacion.png"), dpi=130)

# Gráfico 4: EOQ vs. MILP – número de pedidos
fig, ax = plt.subplots(figsize=(12, 4)); x = np.arange(len(MATERIALES))
ax.bar(x - 0.2, comp["EOQ_pedidos_anio"], 0.4, label="EOQ (pedidos/año)")
ax.bar(x + 0.2, comp["MILP_pedidos"], 0.4, label="MILP (pedidos en 12 meses)")
ax.set_xticks(x, MATERIALES, rotation=45); ax.legend(); ax.set_title("Número de pedidos: EOQ vs. modelo optimizado")
fig.tight_layout(); fig.savefig(os.path.join(RUTA_SALIDA, "g4_eoq_vs_milp.png"), dpi=130)
plt.close("all")

# Exportación a Excel
with pd.ExcelWriter(os.path.join(RUTA_SALIDA, "Etapa6_Resultados_modelo_base_SINTETICO.xlsx")) as w:
    pd.DataFrame({"NOTA": ["DATOS SINTÉTICOS con fines académicos.",
                           f"Escenario E0 (base). Estado del solver: {res['estado']}.",
                           "Q = cantidad pedida en el mes (llega L meses después)."]}).to_excel(w, "LEEME", index=False)
    resumen.to_excel(w, "Resumen", index=False)
    pd.Series(costos, name="COP").to_frame().to_excel(w, "Estructura_costos")
    kpi.to_excel(w, "Indicadores_material")
    for n in ["Q", "Llegadas", "I", "F", "U"]:
        res[n].set_axis(PERIODOS, axis=1).to_excel(w, {"Q": "Plan_pedidos", "Llegadas": "Llegadas",
                                                      "I": "Inventario_final", "F": "Faltantes",
                                                      "U": "Deficit_SS"}[n])
    P["R"].set_axis(PERIODOS, axis=1).to_excel(w, "Pedidos_en_transito")
    comp.to_excel(w, "EOQ_vs_MILP")
    validacion.to_excel(w, "Validacion", index=False)
print("Resultados exportados.")