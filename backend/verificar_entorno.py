
import sys
import pandas as pd
import pulp
import fastapi
import sqlalchemy
import pymysql

print("=" * 45)
print("       REM INVENTORY")
print("       Verificación del entorno")
print("=" * 45)

print("Python:", sys.version.split()[0])
print("Pandas:", pd.__version__)
print("PuLP:", pulp.__version__)
print("FastAPI:", fastapi.__version__)
print("SQLAlchemy:", sqlalchemy.__version__)

# Comprobar el solucionador matemático
modelo = pulp.LpProblem("Prueba_REM", pulp.LpMinimize)

x = pulp.LpVariable("unidades", lowBound=0, cat="Integer")

modelo += x
modelo += x >= 10

modelo.solve(pulp.PULP_CBC_CMD(msg=False))

print("\nEstado del optimizador:", pulp.LpStatus[modelo.status])
print("Cantidad óptima:", pulp.value(x))

print("\nEntorno REM Inventory verificado.")
