"""Genera ADMIN_PASSWORD_HASH y SESSION_SECRET para el panel del cotizador (igual que hash-password.mjs).

Uso (Windows, en la carpeta del proyecto):  python cotizador\\scripts\\hash_password.py
La contraseña no se muestra al escribirla ni se guarda en ningún lado.
Copia las dos líneas que imprime en Cloudflare → jmcambios → Configuración → Variables y secretos (tipo Secreto).
"""

import base64
import getpass
import hashlib
import os
import sys

ITERATIONS = 100_000  # el máximo que acepta Cloudflare para PBKDF2


def make_hash(password: str, salt: bytes, iterations: int = ITERATIONS) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, 32)
    return f"pbkdf2${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def main() -> int:
    pw = getpass.getpass("Contraseña del panel (mínimo 10 caracteres, no se ve al escribir): ")
    if len(pw) < 10:
        print("Muy corta: usa al menos 10 caracteres.")
        return 1
    if getpass.getpass("Repítela: ") != pw:
        print("No coinciden. Vuelve a intentarlo.")
        return 1
    print("\nADMIN_PASSWORD_HASH")
    print(make_hash(pw, os.urandom(16)))
    print("\nSESSION_SECRET")
    print(base64.b64encode(os.urandom(32)).decode())
    print("\nCopia cada valor completo (sin espacios) en Cloudflare como Secreto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
