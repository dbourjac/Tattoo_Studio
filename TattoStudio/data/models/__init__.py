# data/models/__init__.py
def load_all_models():
    # Importa todos los modelos para que SQLAlchemy conozca las clases antes de configurar relaciones
    from .client import Client  # noqa: F401
    from .artist import Artist  # noqa: F401
    from .session_tattoo import TattooSession  # noqa: F401
    from .transaction import Transaction  # noqa: F401
    from .product import Product  # noqa: F401
    from .setting import Setting  # noqa: F401
    from .portfolio import PortfolioItem  # noqa: F401
    from .user import User  # noqa: F401
