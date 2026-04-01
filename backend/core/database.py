from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

@event.listens_for(Base, "init", propagate=True)
def apply_column_defaults(target, args, kwargs):
    """Apply mapped_column defaults at Python instantiation time.

    SQLAlchemy only fires column defaults at flush/insert; this listener
    ensures defaults are visible on newly-constructed objects, which lets
    unit tests assert on default field values without a real DB session.
    """
    for col in target.__mapper__.columns:
        if col.name not in kwargs and col.default is not None:
            if col.default.is_scalar:
                kwargs.setdefault(col.name, col.default.arg)
            elif col.default.is_callable:
                kwargs.setdefault(col.name, col.default.arg(None))

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
