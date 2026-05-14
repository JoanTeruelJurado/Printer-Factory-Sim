#!/bin/bash
# Arranca los 3 servicios: Supplier API, Factory API, Frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Matar procesos anteriores si los hay
echo "Parando procesos anteriores..."
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "uvicorn supplier_api" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# Borrar supplier.db para que el esquema nuevo se aplique limpio
# (los datos se recrean automáticamente desde seed_supplier_data)
echo "Recreando supplier.db con esquema actualizado..."
rm -f "$SCRIPT_DIR/supplier.db"

# Compilar el frontend (rápido si no hay cambios)
echo "Compilando frontend..."
cd frontend && npm run build --silent && cd ..

# Activar virtualenv
source venv/bin/activate

echo ""
echo "=== Arrancando Supplier API (puerto 8001) ==="
python -m uvicorn supplier_api.main:app --host 0.0.0.0 --port 8001 > /tmp/supplier.log 2>&1 &
SUPPLIER_PID=$!
echo "PID: $SUPPLIER_PID  |  Logs: /tmp/supplier.log"

sleep 2

echo ""
echo "=== Arrancando Factory API (puerto 8000) ==="
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/factory.log 2>&1 &
FACTORY_PID=$!
echo "PID: $FACTORY_PID  |  Logs: /tmp/factory.log"

sleep 2

sleep 3

echo ""
echo "==========================================="
echo "  Todo arrancado. Abre en el navegador:"
echo ""
echo "  Juego (frontend + api): http://$(hostname -I | awk '{print $1}'):8000"
echo "  API docs:               http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "  Supplier API:           http://$(hostname -I | awk '{print $1}'):8001/docs"
echo ""
echo "  Para parar todo:  ./stop.sh"
echo "==========================================="
