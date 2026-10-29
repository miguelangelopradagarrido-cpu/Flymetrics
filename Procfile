web: bash -c "if [ -f main.py ]; then uvicorn main:app --host 0.0.0.0 --port ${PORT:-3000}; else uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-3000}; fi"
