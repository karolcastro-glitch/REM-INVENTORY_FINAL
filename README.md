# REM Inventory

Aplicación para explorar inventario y bodegas, ejecutar escenarios de optimización y consultar planes de abastecimiento.

## Requisitos

- Python y MySQL para el backend.
- Node.js y npm para el frontend.
- Una base MySQL con las tablas requeridas por el modelo.

## Preparar el backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Completa `backend/.env` con los datos de conexión de tu propia base MySQL. No compartas ese archivo ni lo subas al repositorio.

Inicia la API desde la carpeta `backend`:

```powershell
uvicorn main:app --reload
```

La API queda disponible en `http://127.0.0.1:8000`.

## Preparar el frontend

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abre la dirección local que indique Vite, normalmente `http://127.0.0.1:5173`.

## Datos de ejemplo

Los archivos de `data/` contienen libros de Excel sintéticos para el trabajo de preparación y análisis. Los CSV generados por las optimizaciones se mantienen fuera del repositorio.
