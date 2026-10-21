"""Emite boletas exentas en eboleta.sii.cl con los montos de la columna D del Excel.

Corre en el computador de JM Cambios con Chrome. La clave del SII la escribe la persona en Chrome;
este programa nunca la pide, la ve ni la guarda. Cada boleta emitida se anota en boletas_emitidas.csv
y una fila ya anotada no se vuelve a emitir.

Uso (PowerShell, dentro de la carpeta boletas):
  python boletas.py diagnostico                                      # anota qué tiene la página de emitir
  python boletas.py practica  --excel "C:\\ruta\\libro.xlsx" --desde 10026 --hasta 10030   # llena sin emitir
  python boletas.py emitir    --excel "C:\\ruta\\libro.xlsx" --desde 10026 --hasta 10030
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMITIR_URL = "https://eboleta.sii.cl/emitir/"
PROFILE_DIR = HERE / ".perfil-chrome"  # sesión de Chrome solo para este programa (no se sube a GitHub)
LOG = HERE / "boletas_emitidas.csv"
SHEET = "SEGUNDA HOJA"
COLUMN = "D"
FOLIO_RE = re.compile(r"BOLETA\s+EXENTA\s+ELECTR[OÓ]NICA\s+N[UÚ]MERO\s*:?\s*([\d.]+)", re.I)


@dataclass(frozen=True)
class Pending:
    row: int
    amount: int


# ------------------------------------------------------------------ Excel y registro

def to_amount(value: object) -> int | None:
    """Monto entero en pesos: 14985, 14985.0 o "14.985". Vacío, texto o ≤ 0 → None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            return None
    else:
        t = str(value).strip().replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            d = Decimal(t)
        except InvalidOperation:
            return None
    if d <= 0 or d != d.to_integral_value():
        return None  # con decimales no se emite: mejor revisarlo a mano
    return int(d)


def read_rows(path: Path, first: int, last: int, sheet: str = SHEET, column: str = COLUMN) -> list[tuple[int, int | None, object]]:
    """(fila, monto, valor original) de la columna indicada. Lee el valor calculado de las fórmulas (=B-C)."""
    from openpyxl import load_workbook

    if path.suffix.lower() != ".xlsx":
        raise SystemExit("El libro debe ser .xlsx (en Excel: Archivo → Guardar como → Libro de Excel).")
    wb = load_workbook(path, data_only=True, read_only=True)
    if sheet not in wb.sheetnames:
        raise SystemExit(f'No encuentro la hoja "{sheet}". Hojas del libro: {", ".join(wb.sheetnames)}')
    ws = wb[sheet]
    out = []
    for r in range(first, last + 1):
        raw = ws[f"{column}{r}"].value
        out.append((r, to_amount(raw), raw))
    wb.close()
    return out


def done_rows(log: Path | None = None) -> dict[int, dict]:
    log = log or LOG
    if not log.exists():
        return {}
    with log.open(newline="", encoding="utf-8") as f:
        return {int(x["fila"]): x for x in csv.DictReader(f)}


def record(row: int, amount: int, folio: str, log: Path | None = None) -> None:
    log = log or LOG
    new = not log.exists()
    with log.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["fila", "monto", "folio", "fecha_hora"])
        w.writerow([row, amount, folio, datetime.now().isoformat(timespec="seconds")])


def plan(rows, done) -> tuple[list[Pending], list[str]]:
    """Separa lo que se emite de lo que se salta (ya emitida, vacía o con monto raro)."""
    todo, notes = [], []
    for r, amount, raw in rows:
        if r in done:
            notes.append(f"fila {r}: ya emitida (folio {done[r]['folio']})")
        elif amount is None:
            if raw not in (None, ""):
                notes.append(f"fila {r}: monto no válido ({raw!r}), se salta")
        else:
            todo.append(Pending(r, amount))
    return todo, notes


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------ Chrome

def open_browser(pw):
    PROFILE_DIR.mkdir(exist_ok=True)
    try:
        ctx = pw.chromium.launch_persistent_context(PROFILE_DIR, channel="chrome", headless=False, viewport=None)
    except Exception:
        ctx = pw.chromium.launch_persistent_context(PROFILE_DIR, headless=False, viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def ensure_logged_in(page) -> None:
    page.goto(EMITIR_URL)
    input("\nSi Chrome pide entrar al SII, entra TÚ con tu RUT y clave. Cuando veas la pantalla de emitir boleta, presiona Enter aquí… ")
    if "eboleta.sii.cl/emitir" not in page.url:
        page.goto(EMITIR_URL)


def first_visible(locators, timeout: int = 1500):
    for loc in locators:
        try:
            loc.first.wait_for(state="visible", timeout=timeout)
            return loc.first
        except Exception:
            continue
    return None


def choose_exenta(page) -> bool:
    """Marca "Exenta" si la pantalla tiene esa opción. En eboleta (oct. 2026) no aparece en la pantalla de emitir:
    el tipo lo confirma la boleta emitida, que debe decir BOLETA EXENTA (si no, el programa se detiene)."""
    re_ex = re.compile(r"exent", re.I)
    for sel in page.locator("select").all():
        options = sel.locator("option").all_inner_texts()
        match = next((o for o in options if re_ex.search(o)), None)
        if match:
            sel.select_option(label=match)
            return True
    el = first_visible([page.get_by_role("radio", name=re_ex), page.get_by_label(re_ex), page.get_by_role("tab", name=re_ex),
                        page.get_by_role("button", name=re_ex)], timeout=800)
    if el is None:
        return False
    if el.get_attribute("type") in ("radio", "checkbox"):
        el.check()
    else:
        el.click()
    return True


def amount_on_screen(page, amount: int, before: str) -> bool:
    """¿La pantalla muestra el monto? Sirve una casilla con ese número, o que "14.985" aparezca en el texto
    de la página después de marcarlo (y no estuviera antes)."""
    for box in page.locator("input[type=text], input[type=tel], input[type=number]").all():
        try:
            if re.sub(r"\D", "", box.input_value()) == str(amount):
                return True
        except Exception:
            continue
    pat = re.compile(r"(?<![\d.])" + re.escape(fmt(amount)) + r"(?![\d.])") if amount >= 1000 else re.compile(r"\$\s*" + str(amount) + r"(?!\d)")
    after = page.locator("body").inner_text()
    return len(pat.findall(after)) > len(pat.findall(before))


def fill_amount(page, amount: int) -> None:
    """eboleta usa un teclado en pantalla (0–9, delete, backspace): se borra y se marcan los dígitos.
    Después se comprueba que la casilla muestre exactamente el monto; si no, no se emite."""
    key = lambda name: page.get_by_role("button", name=name, exact=True)
    before = page.locator("body").inner_text()
    if key("0").count():
        if key("delete").count():
            key("delete").first.click()
        for ch in str(amount):
            key(ch).first.click()
    else:
        box = page.locator("input[type=text]").first
        if not box.count():
            raise RuntimeError("no encontré dónde escribir el monto")
        box.fill(str(amount))
    page.wait_for_timeout(300)
    if not amount_on_screen(page, amount, before):
        raise RuntimeError(f"no veo el monto {fmt(amount)} en la pantalla después de marcarlo")


def pick_exenta_after_emit(page) -> None:
    """Tras apretar EMITIR, eboleta pregunta el tipo de boleta: se elige la opción que dice "exenta"."""
    re_ex = re.compile(r"exent", re.I)
    el = first_visible([page.get_by_role("button", name=re_ex), page.get_by_role("radio", name=re_ex), page.get_by_role("option", name=re_ex),
                        page.get_by_role("listitem").filter(has_text=re_ex), page.get_by_text(re_ex)], timeout=5000)
    if el is None:
        raise RuntimeError('después de EMITIR no apareció la opción "Exenta"')
    if el.get_attribute("type") in ("radio", "checkbox"):
        el.check()
    else:
        el.click()


def emit(page) -> None:
    btn = first_visible([page.get_by_role("button", name=re.compile(r"^\s*emitir\s*$", re.I)), page.get_by_text(re.compile(r"^\s*emitir\s*$", re.I))])
    if btn is None:
        raise RuntimeError('no encontré el botón "Emitir"')
    btn.click()
    pick_exenta_after_emit(page)
    # Si el SII pide confirmar, se confirma (solo en modo emitir).
    ok = first_visible([page.get_by_role("button", name=re.compile(r"^\s*(s[ií]|confirmar|aceptar|continuar|emitir)\s*$", re.I))], timeout=2000)
    if ok is not None:
        ok.click()


def read_folio(page, amount: int, timeout_s: int = 30) -> str:
    """Espera la boleta emitida, comprueba el monto y devuelve el número (folio)."""
    deadline = datetime.now().timestamp() + timeout_s
    while datetime.now().timestamp() < deadline:
        text = page.locator("body").inner_text()
        m = FOLIO_RE.search(text)
        if m:
            if fmt(amount) not in text and str(amount) not in text:
                raise RuntimeError(f"la boleta {m.group(1)} no muestra el monto {fmt(amount)}: revísala en el SII")
            return m.group(1)
        page.wait_for_timeout(500)
    raise RuntimeError("no apareció el número de la boleta emitida")


# ------------------------------------------------------------------ comandos

DUMP_JS = """() => {
  const vis = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const lab = (el) => (el.labels && el.labels[0] ? el.labels[0].innerText : '') || el.getAttribute('aria-label') || el.placeholder || '';
  const out = [];
  document.querySelectorAll('input, select, textarea, button, [role=button], [role=radio], [role=tab], [role=option], [role=listitem], .v-list-item, a').forEach((el) => {
    if (!vis(el) || el.type === 'password' || el.type === 'hidden') return;
    const val = 'value' in el && el.tagName !== 'BUTTON' && el.value ? ` valor="${String(el.value).slice(0, 30)}"` : '';
    const opts = el.tagName === 'SELECT' ? ' opciones=' + [...el.options].map((o) => o.text).join(' | ') : '';
    out.push(`${el.tagName.toLowerCase()} role=${el.getAttribute('role') || ''} type=${el.type || ''} id=${el.id} texto="${(el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 50)}" etiqueta="${lab(el).trim().slice(0, 40)}"${val}${opts}`);
  });
  document.querySelectorAll('[role=dialog], .v-dialog, .v-overlay__content, .modal').forEach((d) => {
    if (vis(d)) out.push('VENTANA: ' + d.innerText.trim().replace(/\\s+/g, ' ').slice(0, 300));
  });
  return out;
}"""


def cmd_diagnostico(args) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx, page = open_browser(pw)
        ensure_logged_in(page)
        problem = None
        if args.tras_emitir:
            # Marca $1.000 y aprieta EMITIR solo para ver la ventana del tipo de boleta; NO elige nada.
            try:
                fill_amount(page, 1000)
                btn = first_visible([page.get_by_role("button", name=re.compile(r"^\s*emitir\s*$", re.I))])
                if btn is None:
                    raise RuntimeError('no encontré el botón "EMITIR"')
                btn.click()
                page.wait_for_timeout(2500)
            except Exception as e:  # se anota igual lo que hay en pantalla, sin apretar EMITIR
                problem = str(e)
        info = page.evaluate(DUMP_JS)
        if problem:
            info.insert(0, f"PROBLEMA: {problem} (no se apretó EMITIR)")
        page.screenshot(path=str(HERE / "diagnostico_eboleta.png"))
        target = HERE / "diagnostico_eboleta.txt"
        target.write_text(f"{page.url}\n" + "\n".join(info), encoding="utf-8")
        print(f"\nListo: {len(info)} elementos anotados en {target} (y foto de la pantalla en diagnostico_eboleta.png)")
        if problem:
            print(f"Ojo: {problem}. No se apretó EMITIR.")
        print("Mándale a Claude una foto o el texto de ese archivo (no contiene tu clave).")
        msg = "NO elijas nada en la ventana de Chrome; sácale foto. " if args.tras_emitir else ""
        input(f"\n{msg}Chrome queda abierto: presiona Enter aquí para cerrarlo… ")
        ctx.close()


def cmd_run(args, really_emit: bool) -> None:
    from playwright.sync_api import sync_playwright

    rows = read_rows(Path(args.excel), args.desde, args.hasta, args.hoja, args.columna)
    todo, notes = plan(rows, done_rows())
    for n in notes:
        print("  ·", n)
    if not todo:
        print("No hay boletas pendientes en ese rango.")
        return
    total = sum(p.amount for p in todo)
    print(f"\n{len(todo)} boletas exentas, total ${fmt(total)}:")
    for p in todo:
        print(f"  fila {p.row}: ${fmt(p.amount)}")
    if really_emit:
        if input(f"\n¿Emitir estas {len(todo)} boletas en el SII? Escribe SI para continuar: ").strip().upper() != "SI":
            print("Cancelado. No se emitió nada.")
            return
    else:
        print("\nMODO PRÁCTICA: llena cada boleta pero NO aprieta Emitir.")

    with sync_playwright() as pw:
        ctx, page = open_browser(pw)
        ensure_logged_in(page)
        emitted = 0
        for p in todo:
            try:
                page.goto(EMITIR_URL)
                page.wait_for_load_state("domcontentloaded")
                exenta = choose_exenta(page)
                fill_amount(page, p.amount)
                if not really_emit:
                    note = "marqué Exenta" if exenta else "no hay opción Exenta en esta pantalla: revisa que tu e-Boleta emita exentas"
                    input(f"fila {p.row}: ${fmt(p.amount)} escrito ({note}). Revisa la pantalla y presiona Enter para la siguiente… ")
                    continue
                emit(page)
                folio = read_folio(page, p.amount)
                record(p.row, p.amount, folio)
                emitted += 1
                print(f"  ✓ fila {p.row}: ${fmt(p.amount)} → boleta N° {folio}")
            except Exception as e:  # cualquier cosa rara: se detiene para no emitir de más
                print(f"\n✗ fila {p.row}: {e}. Me detengo aquí; revisa el SII antes de seguir.")
                input("Presiona Enter para cerrar Chrome… ")
                break
        if really_emit:
            print(f"\nEmitidas: {emitted} de {len(todo)}. Registro: {LOG}")
        ctx.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Boletas exentas en eboleta.sii.cl desde el Excel (columna D).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diagnostico", help="anota los campos de la página de emitir")
    d.add_argument("--tras-emitir", action="store_true", help="marca $1.000, aprieta EMITIR y anota la ventana del tipo de boleta (sin elegir)")
    for name in ("practica", "emitir"):
        p = sub.add_parser(name)
        p.add_argument("--excel", required=True)
        p.add_argument("--desde", type=int, required=True, help="primera fila del Excel")
        p.add_argument("--hasta", type=int, required=True, help="última fila del Excel")
        p.add_argument("--hoja", default=SHEET)
        p.add_argument("--columna", default=COLUMN)
    args = ap.parse_args(argv)
    if args.cmd == "diagnostico":
        cmd_diagnostico(args)
    else:
        if args.hasta < args.desde or args.hasta - args.desde > 500:
            sys.exit("Rango de filas no válido (máximo 500 por tanda).")
        cmd_run(args, really_emit=args.cmd == "emitir")


if __name__ == "__main__":
    main()
