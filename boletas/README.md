# Boletas exentas desde el Excel

Programa para el computador de JM Cambios: lee los montos de la **columna D** de la hoja **SEGUNDA HOJA**
y emite cada uno como **boleta exenta** en https://eboleta.sii.cl/emitir/, igual que a mano.

- La clave del SII la escribes **tú** en Chrome; el programa no la pide, no la ve y no la guarda.
  Chrome recuerda la sesión en la carpeta `.perfil-chrome` (solo en tu computador).
- Cada boleta emitida queda en `boletas_emitidas.csv` (fila, monto, número de boleta, hora).
  Una fila ya anotada **nunca** se vuelve a emitir.
- Antes de emitir muestra la lista y el total y pide escribir `SI`. Si algo sale raro, se detiene.
- Montos vacíos o con texto se saltan (se avisa en pantalla). Con decimales se redondean al peso, como los muestra
  Excel (23.576,4 → 23.576; desde ,5 sube), y la lista lo indica.
- Montos de **más de $500.000** se saltan (llevan factura exenta, se hacen aparte); se avisa en la lista. Otro tope: `--maximo`.
- La fila se anota justo antes del EMITIR final. Se da por emitida cuando aparece la boleta con IMPRIMIR / DESCARGAR /
  COMPARTIR; el número se lee si el SII lo deja disponible, si no queda `ver-en-SII` y sigue con la siguiente.
  Si la boleta no aparece, se detiene y la fila queda bloqueada como `pendiente` (revisar en el SII).
- Una boleta hecha a mano se anota con `python boletas.py marcar --fila 10039 --monto 96903 --folio 21.940`.
- La pantalla de emitir usa un teclado en pantalla: el programa borra, marca los dígitos y comprueba que la casilla
  muestre exactamente el monto antes de apretar EMITIR. Después de EMITIR, eboleta pregunta el tipo: el programa elige
  **Exenta**. Si la boleta emitida no dice BOLETA EXENTA, se detiene.

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
   python boletas.py diagnostico --tras-emitir   # marca $1.000, aprieta EMITIR y anota la ventana del tipo (no elige nada)
   ```
2. **Práctica**: llena cada boleta (exenta + monto) pero NO aprieta Emitir. Revisas la pantalla y Enter.
   ```
   python boletas.py practica --desde 10026 --hasta 10028
   ```
3. **Emitir**:
   ```
   python boletas.py emitir --desde 10026 --hasta 10040
   ```
   `--desde` y `--hasta` son los números de fila del Excel (máximo 500 por tanda). La primera vez se abre una ventana
   para elegir el libro; después pregunta si usar el mismo (o `--excel "C:\ruta\libro.xlsx"`).

Guarda el Excel antes de correrlo: el programa lee el último valor guardado de la columna D (resultado de `=B-C`).

## Pruebas

`pytest boletas/tests` (incluye una página de prueba que imita eboleta; la página real se confirma con el diagnóstico).
