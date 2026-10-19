"""Alertas por Telegram — FASE 6.

  jmcambios-alertas configurar     # conecta tu bot de Telegram (guiado)
  jmcambios-alertas probar         # envía un mensaje de prueba por los canales configurados

El bot SOLO envía avisos: el sistema no lee ni ejecuta nada que le escribas.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path

from jmcambios.alerts.channels import ChannelError, TelegramChannel, channels_from_settings
from jmcambios.config import Settings
from jmcambios.logging_utils import setup_logging
from jmcambios.tools.set_keys import upsert_env

TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


def configurar(prompt: Callable[[str], str] = getpass.getpass, read: Callable[[str], str] = input,
               env_path: Path = Path(".env"), make: Callable[[str, str], TelegramChannel] = TelegramChannel) -> int:
    print("Configuración de alertas por Telegram\n")
    print("1. En Telegram busca @BotFather (con la palomita azul) y escríbele /newbot")
    print("2. Ponle un nombre, p. ej. 'JM Cambios Alertas', y un usuario que termine en 'bot'")
    print("3. BotFather te da un TOKEN (algo como 123456789:AAH...). Cópialo.\n")
    token = ""
    for _ in range(3):
        token = prompt("Pega el TOKEN del bot y presiona Enter (no se verá en pantalla): ").strip().strip("\"'")
        if TOKEN_RE.match(token):
            break
        print("  ✘ Eso no parece un token de bot (número:letras). Inténtalo de nuevo.")
    else:
        print("\nNo se guardó nada.")
        return 1

    bot = make(token, "")
    chat_id = None
    for _ in range(3):
        read("\n4. Abre tu bot nuevo en Telegram, presiona INICIAR (o escribe /start) y luego vuelve aquí y presiona Enter… ")
        try:
            chats = bot.chat_ids()
        except ChannelError as exc:
            print(f"  ✘ {exc}")
            return 1
        if len(chats) == 1:
            chat_id = chats[0][0]
            break
        if len(chats) > 1:
            for i, (cid, name) in enumerate(chats, 1):
                print(f"  {i}. {name or 'sin nombre'}")
            pick = read("¿Cuál eres tú? Escribe el número: ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(chats):
                chat_id = chats[int(pick) - 1][0]
                break
        else:
            print("  Todavía no veo tu mensaje. Asegúrate de escribirle al bot correcto.")
    if chat_id is None:
        print("\nNo se encontró tu chat. No se guardó nada.")
        return 1

    try:
        make(token, chat_id).send("✅ JM Cambios conectado", "Aquí te llegarán las alertas del monitor. Este bot solo envía avisos.")
    except ChannelError as exc:
        print(f"  ✘ No se pudo enviar el mensaje de prueba: {exc}")
        return 1
    text = env_path.read_text(encoding="utf-8-sig") if env_path.exists() else ""
    env_path.write_text(upsert_env(text, {"JMC_TELEGRAM_BOT_TOKEN": token, "JMC_TELEGRAM_CHAT_ID": chat_id}), encoding="utf-8")
    print("\n✔ Listo: te llegó un mensaje de prueba a Telegram y la configuración quedó guardada en .env")
    print("Reinicia el monitor para que empiece a enviar alertas.")
    return 0


def probar(settings: Settings) -> int:
    channels = channels_from_settings(settings)
    if not channels:
        print("No hay canales configurados. Ejecuta: jmcambios-alertas configurar")
        return 1
    ok = True
    for ch in channels:
        try:
            ch.send("🧪 Prueba de JM Cambios", "Si ves esto, las alertas funcionan.")
            print(f"✔ {ch.name}: enviado")
        except ChannelError as exc:
            ok = False
            print(f"✘ {ch.name}: {exc}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Alertas por Telegram/correo (Fase 6)")
    p.add_argument("comando", choices=["configurar", "probar"])
    args = p.parse_args(argv)
    settings = Settings()
    setup_logging(logging.WARNING, settings.secret_values())
    return configurar() if args.comando == "configurar" else probar(settings)


if __name__ == "__main__":
    sys.exit(main())
