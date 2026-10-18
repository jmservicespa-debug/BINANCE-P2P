"""Asistente para guardar la API key de lectura en `.env` sin editar el archivo a mano.

Uso:  python -m jmcambios.tools.set_keys

Pide la API Key y la Secret Key (la entrada no se muestra en pantalla), valida
que no estén vacías y las escribe en las líneas BINANCE_API_KEY / BINANCE_API_SECRET
del archivo `.env`, conservando el resto de la configuración.
"""

from __future__ import annotations

import getpass
import re
import sys
from collections.abc import Callable
from pathlib import Path

from jmcambios.logging_utils import mask_key

_VALID = re.compile(r"^[A-Za-z0-9]+$")
EXPECTED_LENGTH = 64


def clean(value: str) -> str:
    # Quita espacios, saltos de línea y comillas que suelen colarse al pegar.
    return value.strip().strip("\"'").strip()


def problems(value: str) -> list[str]:
    if not value:
        return ["está vacía (no se pegó nada)"]
    issues = []
    if not _VALID.match(value):
        issues.append("contiene caracteres no válidos (espacios u otros símbolos)")
    if len(value) != EXPECTED_LENGTH:
        issues.append(f"tiene {len(value)} caracteres; las claves HMAC de Binance suelen tener {EXPECTED_LENGTH}")
    return issues


def upsert_env(text: str, values: dict[str, str]) -> str:
    lines = text.splitlines()
    pending = dict(values)
    for i, line in enumerate(lines):
        for key in list(pending):
            if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                lines[i] = f"{key}={pending.pop(key)}"
    lines.extend(f"{k}={v}" for k, v in pending.items())
    return "\n".join(lines) + "\n"


def ask(label: str, prompt: Callable[[str], str], attempts: int = 3) -> str | None:
    for _ in range(attempts):
        value = clean(prompt(f"Pega tu {label} y presiona Enter (no se verá en pantalla): "))
        issues = problems(value)
        if not issues:
            print(f"  ✔ {label} recibida: {mask_key(value)} ({len(value)} caracteres)")
            return value
        if value and all("caracteres;" in i for i in issues):
            print(f"  ⚠ {label}: {issues[0]}. Se guardará igualmente; revisa que esté completa.")
            return value
        print(f"  ✘ {label}: " + "; ".join(issues) + ". Inténtalo de nuevo.")
    return None


def main(argv: list[str] | None = None, prompt: Callable[[str], str] = getpass.getpass, env_path: Path = Path(".env")) -> int:
    print("Configuración de la API key de SOLO LECTURA de Binance\n")
    if not env_path.exists():
        example = Path(".env.example")
        env_path.write_text(example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8")

    key = ask("API Key", prompt)
    if key is None:
        print("\nNo se guardó nada. Copia de nuevo la API Key desde Binance y repite.")
        return 1
    secret = ask("Secret Key", prompt)
    if secret is None:
        print("\nNo se guardó nada. Si ya no ves la Secret Key en Binance, crea una API key nueva.")
        return 1
    if key == secret:
        print("\n✘ La API Key y la Secret Key son iguales; seguramente pegaste la misma dos veces. No se guardó nada.")
        return 1

    text = env_path.read_text(encoding="utf-8-sig")
    env_path.write_text(upsert_env(text, {"BINANCE_API_KEY": key, "BINANCE_API_SECRET": secret}), encoding="utf-8")
    print(f"\nGuardado en {env_path.resolve()}")
    print("Siguiente paso:  jmcambios-verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
