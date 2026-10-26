import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.infrastructure.config.settings import settings

DATABASE_URL = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset=utf8mb4"

connect_args = {}
ca_path = getattr(settings, 'DB_SSL_CA', None)
if ca_path:
    # Si la ruta es relativa (ej: ca.pem), resolverla contra la carpeta backend o cwd
    if not os.path.isabs(ca_path):
        from app.infrastructure.config.settings import _BACKEND_DIR
        candidate = _BACKEND_DIR / ca_path
        if candidate.exists():
            ca_path = str(candidate)
        elif os.path.exists(ca_path):
            ca_path = os.path.abspath(ca_path)
    
    if os.path.exists(ca_path):
        connect_args["ssl"] = {"ca": ca_path}

# Crear el motor de SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800
)

# Crear fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos declarativos
Base = declarative_base()

# Generador de sesión de base de datos para dependencias de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
