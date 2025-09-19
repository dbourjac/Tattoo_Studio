def load_all_models():
    # Importar aquí hace que SQLAlchemy 'vea' todas las tablas al crear el esquema
    from . import client, artist, session_tattoo, transaction, product, user, setting, portfolio  # noqa: F401
