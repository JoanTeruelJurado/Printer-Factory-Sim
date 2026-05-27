#!/bin/bash
# Arranca los 3 servicios: Provider API (8001), Manufacturer API (8002), Retailer API (8003)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Matar procesos anteriores si los hay
echo "Parando procesos anteriores..."
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "uvicorn supplier_api" 2>/dev/null || true
pkill -f "uvicorn retailer" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# Borrar DBs para que el esquema nuevo se aplique limpio
echo "Recreando bases de datos con esquema actualizado..."
rm -f "$SCRIPT_DIR/simulator.db"
rm -f "$SCRIPT_DIR/supplier.db"
rm -f "$SCRIPT_DIR/retailer.db"

# Compilar el frontend (rápido si no hay cambios)
echo "Compilando frontend..."
cd frontend && npm run build --silent && cd ..

# Activar virtualenv
source venv/bin/activate

echo ""
echo "=== Arrancando Provider API (puerto 8001) ==="
python -m uvicorn supplier_api.main:app --host 0.0.0.0 --port 8001 > /tmp/supplier.log 2>&1 &
SUPPLIER_PID=$!
echo "PID: $SUPPLIER_PID  |  Logs: /tmp/supplier.log"

sleep 2

echo ""
echo "=== Arrancando Manufacturer API (puerto 8002) ==="
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > /tmp/factory.log 2>&1 &
FACTORY_PID=$!
echo "PID: $FACTORY_PID  |  Logs: /tmp/factory.log"

sleep 2

echo ""
echo "=== Arrancando Retailer API (puerto 8003) ==="
python -m uvicorn retailer.main:app --host 0.0.0.0 --port 8003 > /tmp/retailer.log 2>&1 &
RETAILER_PID=$!
echo "PID: $RETAILER_PID  |  Logs: /tmp/retailer.log"

sleep 2

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "==========================================="
echo "  Todo arrancado. Abre en el navegador:"
echo ""
echo "  Juego (frontend):  http://$IP:8002"
echo "  Manufacturer API:  http://$IP:8002/docs"
echo "  Provider API:      http://$IP:8001/docs"
echo "  Retailer API:      http://$IP:8003/docs"
echo ""
echo "  Para parar todo:  ./stop.sh"
echo "==========================================="
