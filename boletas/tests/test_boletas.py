import builtins
from pathlib import Path

import pytest
from openpyxl import Workbook

import boletas as b


def test_montos():
    assert b.to_amount(14985) == 14985
    assert b.to_amount(14985.0) == 14985
    assert b.to_amount("14.985") == 14985
    assert b.to_amount("$ 9.990") == 9990
    assert b.to_amount(None) is None
    assert b.to_amount("") is None
    assert b.to_amount(0) is None
    assert b.to_amount(-5) is None
    assert b.to_amount(10.5) == 11  # con decimales: redondeo normal
    assert b.to_amount(23576.4) == 23576
    assert b.to_amount(0.4) is None
    assert b.to_amount("hola") is None


def libro(tmp_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "SEGUNDA HOJA"
    for r, (bb, c, d) in {10026: (15000, 15, 14985), 10027: (104530, 105, 104425), 10028: (10000, 10, None), 10029: (1, 1, "x")}.items():
        ws[f"B{r}"], ws[f"C{r}"], ws[f"D{r}"] = bb, c, d
    p = tmp_path / "libro.xlsx"
    wb.save(p)
    return p


def test_excel_registro_y_plan(tmp_path):
    rows = b.read_rows(libro(tmp_path), 10026, 10029)
    assert [(r, a) for r, a, _ in rows] == [(10026, 14985), (10027, 104425), (10028, None), (10029, None)]
    log = tmp_path / "log.csv"
    b.record(10026, 14985, "21.938", log)
    todo, notes = b.plan(rows, b.done_rows(log))
    assert todo == [b.Pending(10027, 104425)]  # la ya emitida y las vacías no se emiten
    assert any("ya emitida (folio 21.938)" in n for n in notes)
    assert any("10029" in n and "no válido" in n for n in notes)
    with pytest.raises(SystemExit):
        b.read_rows(tmp_path / "libro.xls", 1, 2)


def test_folio():
    text = "JM SERVICES SPA\nBOLETA EXENTA ELECTRÓNICA NUMERO:\n21.938\nMonto Total\n$ 14.985"
    assert b.FOLIO_RE.search(text).group(1) == "21.938"


# Página de prueba que imita eboleta (la real puede ser distinta: por eso existe el modo diagnóstico).
FAKE = """<!doctype html><meta charset=utf-8><h1>Emitir e-Boleta</h1>
<input type=text id=input-33 readonly><label><input type=checkbox id=input-48> Calculadora</label>
<button type=button>delete</button><button type=button>backspace</button>
<button type=button>7</button><button type=button>8</button><button type=button>9</button><button type=button>4</button>
<button type=button>5</button><button type=button>6</button><button type=button>1</button><button type=button>2</button>
<button type=button>3</button><button type=button>0</button><button type=button id=e>EMITIR</button><div role=dialog id=tipo hidden><div role=button id=sel>Boleta afecta arrow_drop_down</div><div id=menu hidden><div class=v-list-item id=o1>Boleta afecta</div><div class=v-list-item id=o2>Boleta exenta</div></div><button type=button>EMITIR</button></div><div id=out></div><div id=done hidden><button type=button>print IMPRIMIR</button><a href='#'>get_app DESCARGAR</a><button type=button id=cerrar>CERRAR</button></div>
<script>
const box = document.getElementById('input-33');
document.querySelectorAll('button').forEach((b) => b.onclick = () => {
  const t = b.innerText;
  if (/^\\d$/.test(t)) box.value = Number((box.value.replace(/\\D/g, '') || '') + t).toLocaleString('es-CL');
  if (t === 'delete') box.value = '';
  if (t === 'EMITIR' && b.id === 'e') { document.getElementById('tipo').hidden = false; }
  if (t === 'EMITIR' && b.id !== 'e' && !/exenta/i.test(document.getElementById('sel').innerText)) document.getElementById('out').innerText = 'BOLETA ELECTRÓNICA AFECTA';
  if (t === 'EMITIR' && b.id !== 'e' && /exenta/i.test(document.getElementById('sel').innerText)) { const m = Number(box.value.replace(/\\D/g, ''));
    document.getElementById('done').hidden = false;
    document.getElementById('out').innerText = 'BOLETA EXENTA ELECTRÓNICA NUMERO:\\n' + (21938 + m % 7).toLocaleString('es-CL') + '\\nMonto Total $ ' + m.toLocaleString('es-CL'); }
  if (t === 'CERRAR') { ['done', 'tipo'].forEach((id) => document.getElementById(id).hidden = true); document.getElementById('out').innerText = ''; document.getElementById('sel').innerText = 'Boleta afecta arrow_drop_down'; window.cerrados = (window.cerrados || 0) + 1; }
});
document.getElementById('sel').onclick = () => { document.getElementById('menu').hidden = false; };
['o1', 'o2'].forEach((id) => document.getElementById(id).onclick = (e) => { document.getElementById('sel').innerText = e.target.innerText + ' arrow_drop_down'; document.getElementById('menu').hidden = true; });
</script>"""


def test_emite_en_pagina_de_prueba(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright

    page_file = tmp_path / "emitir.html"
    page_file.write_text(FAKE, encoding="utf-8")
    monkeypatch.setattr(b, "EMITIR_URL", page_file.as_uri())
    log = tmp_path / "log.csv"
    monkeypatch.setattr(b, "LOG", log)
    monkeypatch.setattr(builtins, "input", lambda *_: "SI")
    opened = {}

    def fake_open(pw):
        br = pw.chromium.launch(executable_path=_chromium())
        opened["b"] = br
        ctx = br.new_context()
        return ctx, ctx.new_page()

    monkeypatch.setattr(b, "open_browser", fake_open)
    monkeypatch.setattr(b, "ensure_logged_in", lambda page: None)
    b.main(["emitir", "--excel", str(libro(tmp_path)), "--desde", "10026", "--hasta", "10028"])
    rows = b.done_rows(log)
    assert sorted(rows) == [10026, 10027]
    assert rows[10026]["monto"] == "14985" and rows[10026]["folio"]
    # Segunda pasada: nada pendiente, no se emite de nuevo.
    b.main(["emitir", "--excel", str(libro(tmp_path)), "--desde", "10026", "--hasta", "10028"])
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 5  # encabezado + "pendiente" y folio por boleta; nada nuevo


def _chromium():
    import glob
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    return found[-1] if found else None


def test_monto_mostrado_como_texto(tmp_path, monkeypatch):
    """Si el SII muestra el monto como texto (no en una casilla), igual se reconoce."""
    from playwright.sync_api import sync_playwright

    html = FAKE.replace("<input type=text id=input-33 readonly>", "<div id=input-33>$ 0</div>").replace("box.value", "box.textContent")
    html = html.replace("if (t === 'delete') box.textContent = '';", "if (t === 'delete') box.textContent = '$ 0';")
    html = html.replace("box.textContent = Number(", "box.textContent = '$ ' + Number(")
    html = html.replace("(box.textContent.replace(/\\\\D/g, '') || '')", "(box.textContent.replace(/\\\\D/g, '').replace(/^0+/, '') || '')")
    f = tmp_path / "e.html"
    f.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=_chromium())
        page = br.new_page()
        page.goto(f.as_uri())
        b.fill_amount(page, 14985)
        assert "14.985" in page.locator("#input-33").inner_text()
        with pytest.raises(RuntimeError):
            page.evaluate("document.querySelectorAll('button').forEach((x) => { if (/^\\d$/.test(x.innerText)) x.onclick = null; })")
            b.fill_amount(page, 2000)
        br.close()


def test_practica_no_emite(tmp_path, monkeypatch, capsys):
    from playwright.sync_api import sync_playwright  # noqa: F401

    page_file = tmp_path / "emitir.html"
    page_file.write_text(FAKE, encoding="utf-8")
    monkeypatch.setattr(b, "EMITIR_URL", page_file.as_uri())
    log = tmp_path / "log.csv"
    monkeypatch.setattr(b, "LOG", log)
    monkeypatch.setattr(builtins, "input", lambda *_: "")
    monkeypatch.setattr(b, "ensure_logged_in", lambda page: None)

    def fake_open(pw):
        ctx = pw.chromium.launch(executable_path=_chromium()).new_context()
        return ctx, ctx.new_page()

    monkeypatch.setattr(b, "open_browser", fake_open)
    b.main(["practica", "--excel", str(libro(tmp_path)), "--desde", "10026", "--hasta", "10026"])
    out = capsys.readouterr().out
    assert "ventana en Boleta exenta" in out and "EMITIR" in out
    assert not log.exists()  # nada emitido


def test_formula_sin_valor_guardado(tmp_path):
    """Libro guardado sin el resultado de =B-C (pasa con algunos programas): se calcula la resta."""
    wb = Workbook()
    ws = wb.active
    ws.title = "SEGUNDA HOJA"
    ws["B10039"], ws["C10039"], ws["D10039"] = 10000, 10, "=B10039-C10039"
    ws["B10040"], ws["C10040"], ws["D10040"] = 5000, 5, "=B10039-C10040"  # fórmula rara: no se adivina
    p = tmp_path / "f.xlsx"
    wb.save(p)  # openpyxl no guarda resultados de fórmulas
    rows = b.read_rows(p, 10039, 10040)
    assert [(r, a) for r, a, _ in rows] == [(10039, 9990), (10040, None)]


def test_boleta_como_imagen_se_anota_y_sigue(tmp_path, monkeypatch):
    """El SII muestra la boleta como imagen (sin texto): con IMPRIMIR/DESCARGAR a la vista se da por emitida y sigue."""
    html = FAKE.replace("document.getElementById('out').innerText = 'BOLETA EXENTA", "document.getElementById('out').dataset.x = 'BOLETA EXENTA")
    log = _run(tmp_path, monkeypatch, html)
    rows = b.done_rows(log)
    assert sorted(rows) == [10026, 10027]
    assert {r["folio"] for r in rows.values()} == {"ver-en-SII"}
    assert (tmp_path / "diagnostico_boleta_emitida.txt").exists()


def test_sin_senal_de_emitida_se_detiene_y_bloquea(tmp_path, monkeypatch):
    html = FAKE.replace("document.getElementById('out').innerText = 'BOLETA EXENTA", "document.getElementById('out').dataset.x = 'BOLETA EXENTA")
    html = html.replace("document.getElementById('done').hidden = false;", "")
    monkeypatch.setattr(b, "read_folio", lambda page, amount, responses, timeout_s=30: b.__dict__["_rf"](page, amount, responses, 3))
    log = _run(tmp_path, monkeypatch, html)
    rows = b.done_rows(log)
    assert list(rows) == [10026] and rows[10026]["folio"] == "pendiente"  # bloqueada, no se repite; no siguió


_ORIG_READ = b.read_folio
b._rf = _ORIG_READ


def _run(tmp_path, monkeypatch, html):
    page_file = tmp_path / "emitir.html"
    page_file.write_text(html, encoding="utf-8")
    monkeypatch.setattr(b, "EMITIR_URL", page_file.as_uri())
    monkeypatch.setattr(b, "HERE", tmp_path)
    log = tmp_path / "log.csv"
    monkeypatch.setattr(b, "LOG", log)
    monkeypatch.setattr(builtins, "input", lambda *_: "SI")
    monkeypatch.setattr(b, "ensure_logged_in", lambda page: None)

    def fake_open(pw):
        ctx = pw.chromium.launch(executable_path=_chromium()).new_context()
        return ctx, ctx.new_page()

    monkeypatch.setattr(b, "open_browser", fake_open)
    b.main(["emitir", "--excel", str(libro(tmp_path)), "--desde", "10026", "--hasta", "10027"])
    return log


def test_marcar_a_mano(tmp_path, monkeypatch):
    log = tmp_path / "log.csv"
    monkeypatch.setattr(b, "LOG", log)
    b.main(["marcar", "--fila", "10039", "--monto", "96903", "--folio", "21.940"])
    assert b.done_rows(log)[10039]["folio"] == "21.940"
    assert b.folio_in_json({"data": {"folio": 21940, "monto": 96903}}) == "21940"
    assert b.folio_in_json({"x": [{"nroFolio": "21.941"}]}) == "21.941"
    assert b.folio_in_json({"monto": 1}) is None


def test_desmarcar(tmp_path, monkeypatch):
    log = tmp_path / "log.csv"
    monkeypatch.setattr(b, "LOG", log)
    b.main(["marcar", "--fila", "10031", "--monto", "23576", "--folio", "21957"])
    b.main(["desmarcar", "--fila", "10031"])
    assert 10031 not in b.done_rows(log)
    b.main(["marcar", "--fila", "10031", "--monto", "23576", "--folio", "21960"])
    assert b.done_rows(log)[10031]["folio"] == "21960"
