# 3D Printer Factory Simulator

A FastAPI-based discrete-event simulation of a 3D printer production factory.

## Getting started

1. Create a Python environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

3. Open the API docs:
   - http://127.0.0.1:8000/docs
   - http://127.0.0.1:8000/redoc

## Project layout

- `app/main.py` - FastAPI application entrypoint
- `app/db/database.py` - SQLite engine and session management
- `app/db/models.py` - SQLAlchemy ORM schema
- `app/api/game.py` - game management endpoints
- `app/services/seed.py` - initial data seeding

## Notes

- The application uses `sqlite:///./simulator.db` by default unless `DATABASE_URL` is set.
- The database schema is created automatically on startup.
