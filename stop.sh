#!/bin/bash
echo "Parando todos los servicios..."
pkill -f "uvicorn app.main" 2>/dev/null && echo "Factory API parada" || true
pkill -f "uvicorn supplier_api" 2>/dev/null && echo "Supplier API parada" || true
pkill -f "vite" 2>/dev/null || true
echo "Hecho."
