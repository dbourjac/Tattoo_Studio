# tattoo_cli.py
# TattooStudio — Esqueleto CLI (solo Python: sin PyQt, sin BD)
# Navegación: Studio / Scheduler / Clients / Staff / Reports / Forms
# CTAs en Studio: New Client, Return Client, Portfolios, Queue
# Comandos globales: L (Language), U (Switch User), S (Settings), I (Info), B (Backup), Q (Quit)

import os
import sys
from datetime import datetime

VERSION = "0.0.1"

state = {
    "page": 0,  # 0=Studio, 1=Scheduler, 2=Clients, 3=Staff, 4=Reports, 5=Forms
    "language": "English",  # ó "Español" (solo mostramos el valor)
    "user": {"name": "Dylan Bourjac", "role": "Tatuador", "email": "dbourjac@hotmail.com"},
    "last_backup": "—",
}

PAGES = ["Studio", "Scheduler", "Clients", "Staff", "Reports", "Forms"]


# ---------- utilidades ----------
def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\n[Enter] para continuar...")


def title(s: str):
    print("=" * len(s))
    print(s)
    print("=" * len(s))


def draw_topbar():
    brand = "TatooStudio"
    nav = " | ".join(
        f"[{i+1}] {name.upper() if i == state['page'] else name}"
        for i, name in enumerate(PAGES)
    )
    print(brand)
    print("-" * max(len(brand), len(nav)))
    print(nav)
    print("-" * max(len(brand), len(nav)))


def draw_statusbar():
    print("\n" + "-" * 70)
    print(f"Ver. {VERSION} | Last Backup: {state['last_backup']} | Language: {state['language']}")
    print("Comandos globales: [L]anguage  [U]ser  [S]ettings  [I]nfo  [B]ackup  [Q]uit")
    print("-" * 70)


# ---------- acciones globales ----------
def set_language():
    clear()
    title("Language / Idioma")
    print("1) English")
    print("2) Español")
    choice = input("Selecciona (1/2): ").strip()
    if choice == "1":
        state["language"] = "English"
    elif choice == "2":
        state["language"] = "Español"
    else:
        print("Opción no válida.")
    pause()


def switch_user():
    clear()
    title("Switch User (simulado)")
    new_name = input("Nombre de usuario (enter para mantener): ").strip()
    new_role = input("Rol (Admin/Recepcionista/Tatuador): ").strip()
    new_mail = input("Email: ").strip()
    if new_name:
        state["user"]["name"] = new_name
    if new_role:
        state["user"]["role"] = new_role
    if new_mail:
        state["user"]["email"] = new_mail
    print("\nUsuario actualizado (simulado).")
    pause()


def settings():
    clear()
    title("Settings (simulado)")
    print("Aquí irían preferencias del sistema, tema, atajos, etc.")
    pause()


def info():
    clear()
    title("Info")
    print("TattooStudio — CLI demo (sin GUI, sin BD).")
    print("Objetivo: practicar estructura y flujo antes de la interfaz gráfica.")
    pause()


def backup_now():
    state["last_backup"] = datetime.now().strftime("%H:%M:%S")
    print(f"\nBackup simulado a las {state['last_backup']}.")
    pause()


# ---------- páginas ----------
def page_studio():
    clear()
    draw_topbar()

    # “Hero” centrado (ASCII logo simple)
    print("\n" * 1)
    print("      (•_•)   ")
    print("     <)   )╯   TatooStudio")
    print("      /   \\   ")
    print("\nBienvenido/a. Acciones rápidas:")

    # CTAs
    print("\n[CTAs]")
    print("  [A] New Client")
    print("  [R] Return Client")
    print("  [P] Portfolios")
    print("  [Q] Queue")

    # Tarjeta de perfil (panel derecho en GUI; aquí listado)
    print("\n[Perfil actual]")
    u = state["user"]
    print(f"  Nombre: {u['name']}")
    print(f"  Rol:    {u['role']}")
    print(f"  Email:  {u['email']}")
    print("  Acciones: [U] Switch User   [S] Settings   [I] Info")

    draw_statusbar()

    cmd = input("Elige (1..6 navega; A/R/P/Q CTAs; L/U/S/I/B/Q): ").strip().lower()
    handle_global_or_nav(cmd, default_page=0, cta_handler=handle_studio_cta)


def handle_studio_cta(cmd: str):
    if cmd == "a":
        print("\n→ New Client (simulado). Aquí abriríamos un formulario.")
        pause()
    elif cmd == "r":
        print("\n→ Return Client (simulado). Buscaríamos un cliente existente.")
        pause()
    elif cmd == "p":
        print("\n→ Portfolios (simulado). Galería/biblioteca de diseños.")
        pause()
    elif cmd == "q":
        print("\n→ Queue (simulado). Fila de atención actual.")
        pause()


def page_scheduler():
    clear()
    draw_topbar()
    title("Scheduler (simulado)")
    print("Aquí iría un calendario/agenda de citas.")
    print("Acciones típicas: [N]ueva cita, [E]ditar, [C]ancelar (simulado).")
    draw_statusbar()
    cmd = input("Elige (1..6 navega; N/E/C; L/U/S/I/B/Q): ").strip().lower()
    handle_global_or_nav(cmd, default_page=1)


def page_clients():
    clear()
    draw_topbar()
    title("Clients (simulado)")
    print("Listado/gestión de clientes (placeholder).")
    print("Acciones: [N]uevo, [B]uscar, [E]ditar, [X]Eliminar (simulado).")
    draw_statusbar()
    cmd = input("Elige (1..6 navega; N/B/E/X; L/U/S/I/B/Q): ").strip().lower()
    handle_global_or_nav(cmd, default_page=2)


def page_staff():
    clear()
    draw_topbar()
    title("Staff (simulado)")
    print("Gestión de usuarios/tatuadores (placeholder).")
    draw_statusbar()
    cmd = input("Elige (1..6 navega; L/U/S/I/B/Q): ").strip().lower()
    handle_global_or_nav(cmd, default_page=3)


def page_reports():
    clear()
    draw_topbar()
    title("Reports (simulado)")
    print("Reportes y métricas (placeholder).")
    draw_statusbar()
    cmd = input("Elige (1..6 navega; L/U/S/I/B/Q): ").strip().lower()
    handle_global_or_nav(cmd, default_page=4)


def page_forms():
    clear()
    draw_topbar()
    title("Forms (simulado)")
    print("Integraciones/Forms (placeholder).")
    draw_statusbar()
    cmd = input("Elige (1..6 navega; L/U/S/I/B/Q): ").strip().lower()
    handle_global_or_nav(cmd, default_page=5)


# ---------- router / navegación ----------
def handle_global_or_nav(cmd: str, default_page: int, cta_handler=None):
    """Interpreta navegación (1..6), comandos globales (l/u/s/i/b/q) y CTAs por página."""
    global state

    if cmd in {"1", "2", "3", "4", "5", "6"}:
        state["page"] = int(cmd) - 1
        return

    if cmd == "l":
        set_language()
    elif cmd == "u":
        switch_user()
    elif cmd == "s":
        settings()
    elif cmd == "i":
        info()
    elif cmd == "b":
        backup_now()
    elif cmd == "q":
        print("\n¡Nos vemos! 💚")
        sys.exit(0)
    else:
        if cta_handler:
            cta_handler(cmd)
        else:
            print("Opción no válida.")
            pause()

    state["page"] = default_page


def main_loop():
    while True:
        if state["page"] == 0:
            page_studio()
        elif state["page"] == 1:
            page_scheduler()
        elif state["page"] == 2:
            page_clients()
        elif state["page"] == 3:
            page_staff()
        elif state["page"] == 4:
            page_reports()
        elif state["page"] == 5:
            page_forms()
        else:
            state["page"] = 0


if __name__ == "__main__":
    clear()
    print("Arrancando TattooStudio (CLI) — sin GUI, sin BD — solo estructura.\n")
    main_loop()
