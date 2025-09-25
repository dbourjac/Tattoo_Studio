# data/tools/purge_artists.py
from typing import List, Optional
from data.db.session import SessionLocal
from data.models.artist import Artist
from data.models.session_tattoo import TattooSession
from data.models.transaction import Transaction
from data.models.user import User

# ========== CONFIGURA AQUÍ ==========
ARTIST_IDS: List[int] = [9]

# Modo:
# - "purge": elimina sesiones/transacciones de esos artistas y pone user.artist_id=NULL; luego borra artistas.
# - "reassign": reasigna sesiones/transacciones a TARGET_ARTIST_ID (o crea placeholder si CREATE_PLACEHOLDER=True).
MODE: str = "purge"  # "purge" | "reassign"

# Solo si MODE == "reassign":
TARGET_ARTIST_ID: Optional[int] = None  # p.ej. 1  (si lo dejas None y CREATE_PLACEHOLDER=True, se creará uno)
CREATE_PLACEHOLDER: bool = True         # crear artista "(Placeholder)" si no pasaste TARGET_ARTIST_ID
PLACEHOLDER_NAME: str = "(Placeholder)"
PLACEHOLDER_ACTIVE: bool = False
# ====================================


def ensure_target_artist(db) -> Optional[int]:
    """Devuelve el ID de artista destino. Crea uno si así se configura."""
    if MODE != "reassign":
        return None

    if TARGET_ARTIST_ID:
        exists = db.get(Artist, TARGET_ARTIST_ID)
        if not exists:
            raise ValueError(f"TARGET_ARTIST_ID={TARGET_ARTIST_ID} no existe.")
        return TARGET_ARTIST_ID

    if CREATE_PLACEHOLDER:
        a = Artist(name=PLACEHOLDER_NAME, rate_commission=0.0, active=PLACEHOLDER_ACTIVE)
        db.add(a)
        db.flush()  # para obtener a.id
        print(f"Placeholder creado: id={a.id}, name='{a.name}'")
        return int(a.id)

    raise ValueError("MODE='reassign' pero no diste TARGET_ARTIST_ID ni CREATE_PLACEHOLDER=True.")


def main():
    if MODE not in {"purge", "reassign"}:
        raise ValueError("MODE debe ser 'purge' o 'reassign'.")

    ids = [int(x) for x in ARTIST_IDS]
    if not ids:
        print("No hay IDs para procesar.")
        return

    with SessionLocal() as db:
        try:
            target_id = ensure_target_artist(db)

            # Si reassign y el target está en la lista a eliminar, lo quitamos
            if target_id and target_id in ids:
                ids = [i for i in ids if i != target_id]

            if not ids:
                print("Nada que hacer (lista de IDs vacía después de excluir destino).")
                return

            # --- Reporte previo ---
            sess_count = db.query(TattooSession).filter(TattooSession.artist_id.in_(ids)).count()
            tx_count   = db.query(Transaction).filter(Transaction.artist_id.in_(ids)).count()
            user_count = db.query(User).filter(User.artist_id.in_(ids)).count()
            print(f"Dependencias encontradas: sesiones={sess_count}, transacciones={tx_count}, usuarios={user_count}")

            # --- Operaciones según modo ---
            if MODE == "reassign":
                # Reasignar sesiones/transacciones al destino; usuarios quedan sin artista (NULL)
                db.query(TattooSession)\
                  .filter(TattooSession.artist_id.in_(ids))\
                  .update({TattooSession.artist_id: target_id}, synchronize_session=False)

                db.query(Transaction)\
                  .filter(Transaction.artist_id.in_(ids))\
                  .update({Transaction.artist_id: target_id}, synchronize_session=False)

                db.query(User)\
                  .filter(User.artist_id.in_(ids))\
                  .update({User.artist_id: None}, synchronize_session=False)

            else:  # MODE == "purge"
                # Eliminar transacciones y sesiones de esos artistas; usuarios quedan sin artista (NULL)
                deleted_tx = db.query(Transaction)\
                               .filter(Transaction.artist_id.in_(ids))\
                               .delete(synchronize_session=False)
                deleted_sess = db.query(TattooSession)\
                                 .filter(TattooSession.artist_id.in_(ids))\
                                 .delete(synchronize_session=False)
                print(f"Eliminados: transacciones={deleted_tx}, sesiones={deleted_sess}")

                db.query(User)\
                  .filter(User.artist_id.in_(ids))\
                  .update({User.artist_id: None}, synchronize_session=False)

            # Finalmente, borrar artistas
            deleted_art = db.query(Artist).filter(Artist.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
            print(f"Artistas eliminados: {deleted_art}")
            print("OK.")

        except Exception as e:
            db.rollback()
            print("Error:", e)


if __name__ == "__main__":
    main()
