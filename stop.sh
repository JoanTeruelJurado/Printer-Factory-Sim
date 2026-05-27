#!/bin/bash
echo "Parando todos los servicios..."
pkill -f "uvicorn app.main" 2>/dev/null && echo "Manufacturer API parada" || true
pkill -f "uvicorn supplier_api" 2>/dev/null && echo "Provider API parada" || true
pkill -f "uvicorn retailer" 2>/dev/null && echo "Retailer API parada" || true
pkill -f "vite" 2>/dev/null || true
echo "Hecho."
