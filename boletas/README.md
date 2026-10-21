# Boletas exentas desde el Excel

Programa para el computador de JM Cambios: lee los montos de la **columna D** de la hoja **SEGUNDA HOJA**
y emite cada uno como **boleta exenta** en https://eboleta.sii.cl/emitir/, igual que a mano.

- La clave del SII la escribes **tú** en Chrome; el programa no la pide, no la ve y no la guarda.
  Chrome recuerda la sesión en la carpeta `.perfil-chrome` (solo en tu computador).
- Cada boleta emitida queda en `boletas_emitidas.csv` (fila, monto, número de boleta, hora).
  Una fila ya anotada **nunca** se vuelve a emitir.
- Antes de emitir muestra la lista y el total y pide escribir `SI`. Si algo sale raro, se detiene.
- Montos vacíos, con texto o con decimales se saltan (se avisa en pantalla).

## Instalar (una vez, PowerShell)

```
cd C:\ruta\BINANCE-P2P\boletas
pip install -r requirements.txt
```

Usa el Chrome que ya tienes instalado. El libro debe ser `.xlsx`.

## Usar

1. **Diagnóstico** (la primera vez): abre Chrome, entras al SII, y anota qué casillas y botones tiene la página de
   emitir en `diagnostico_eboleta.txt`. Se lo mandas a Claude para ajustar el programa a la página real.
   ```
   python boletas.py diagnostico
   ```
2. **Práctica**: llena cada boleta (exenta + monto) pero NO aprieta Emitir. Revisas la pantalla y Enter.
   ```
   python boletas.py practica --excel "C:\ruta\JM SERVICES SPA.xlsx" --desde 10026 --hasta 10028
   ```
3. **Emitir**:
   ```
   python boletas.py emitir --excel "C:\ruta\JM SERVICES SPA.xlsx" --desde 10026 --hasta 10040
   ```
   `--desde` y `--hasta` son los números de fila del Excel (máximo 500 por tanda).

Guarda el Excel antes de correrlo: el programa lee el último valor guardado de la columna D (resultado de `=B-C`).

## Pruebas

`pytest boletas/tests` (incluye una página de prueba que imita eboleta; la página real se confirma con el diagnóstico).
