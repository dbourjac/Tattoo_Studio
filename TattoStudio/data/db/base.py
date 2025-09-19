try:
    # SQLAlchemy 2.0+
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        """Base declarativa que usarán todos los modelos (tablas)."""
        pass

except ImportError:
    # Fallback para SQLAlchemy 1.4.x
    from sqlalchemy.orm import declarative_base as _declarative_base
    Base = _declarative_base()
