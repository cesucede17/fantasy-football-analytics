/**
 * Write endpoint for the iOS Shortcuts and the web dashboard (web/).
 *
 * Deployment: Extensions > Apps Script > Deploy > New deployment
 *   Type: Web app | Execute as: me | Access: anyone with the link
 *
 * "Anyone with the link" access is required so the Shortcut and the web
 * dashboard can call it, which is why the token is the only real
 * protection. Make it long. Checked on every request via `_autorizado()`
 * (see doGet.gs).
 *
 * The token does NOT live in this file (which is committed to git). It's
 * stored in Project Settings > Script Properties, key TOKEN. Run
 * `configurarToken()` once from the editor (with the real value pasted in
 * temporarily) and delete it from the code afterward, or paste it directly
 * into the Script Properties UI.
 *
 * `accion` (default "append", so the iPhone Shortcut — which never sends
 * this field — keeps working exactly as before):
 *   - "append": adds each row in `filas` at the end. Same as always.
 *   - "delete_where": deletes rows where every column in `donde` matches
 *     (column: value).
 *   - "update_where": for rows matching `donde`, writes each column:value
 *     from `set` — creates the column at the end if `set` carries one the
 *     tab doesn't have yet (same as marcar_pertenencia).
 *   - "marcar_pertenencia": for every row, checks `valores[columna_valor]`
 *     and writes `si` into `columna_destino` if it's in the `pertenece`
 *     list, or `no` otherwise — built for
 *     actualizar_titulares_mi_plantilla (marks the whole starting lineup
 *     at once).
 */

function configurarToken() {
  // Paste the token here ONLY to run this function once, then delete it.
  PropertiesService.getScriptProperties().setProperty('TOKEN', 'PASTE_HERE_AND_DELETE_AFTERWARD');
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (!_autorizado(data.token)) {
      return _json({ ok: false, error: 'auth' });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const hoja = ss.getSheetByName(data.pestana);
    if (!hoja) throw new Error('tab not found: ' + data.pestana);

    const accion = data.accion || 'append';

    if (accion === 'append') {
      data.filas.forEach(fila => hoja.appendRow(fila));
      return _json({ ok: true, n: data.filas.length });
    }

    if (accion === 'delete_where') {
      return _json({ ok: true, n: _eliminarDonde(hoja, data.donde) });
    }

    if (accion === 'update_where') {
      return _json({ ok: true, n: _actualizarDonde(hoja, data.donde, data.set) });
    }

    if (accion === 'marcar_pertenencia') {
      return _json({ ok: true, n: _marcarPertenencia(hoja, data.columna_valor, data.columna_destino, data.pertenece, data.si, data.no) });
    }

    throw new Error('unknown action: ' + accion);

  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function _filaCoincide(fila, cabecera, donde) {
  return Object.keys(donde).every(col => {
    const idx = cabecera.indexOf(col);
    return idx !== -1 && String(fila[idx]) === String(donde[col]);
  });
}

function _eliminarDonde(hoja, donde) {
  const valores = hoja.getDataRange().getValues();
  const cabecera = valores[0];
  let eliminadas = 0;
  // Bottom to top: deleting a row doesn't shift the ones still to check.
  for (let i = valores.length - 1; i >= 1; i--) {
    if (_filaCoincide(valores[i], cabecera, donde)) {
      hoja.deleteRow(i + 1);
      eliminadas++;
    }
  }
  return eliminadas;
}

function _actualizarDonde(hoja, donde, set) {
  const valores = hoja.getDataRange().getValues();
  const cabecera = valores[0];
  // If `set` carries a column the tab doesn't have yet, create it at the
  // end before writing rows — otherwise the write would silently vanish
  // (idx === -1, no error branch for it).
  Object.keys(set).forEach(col => {
    if (cabecera.indexOf(col) === -1) {
      hoja.getRange(1, cabecera.length + 1).setValue(col);
      cabecera.push(col);
    }
  });
  let actualizadas = 0;
  for (let i = 1; i < valores.length; i++) {
    if (_filaCoincide(valores[i], cabecera, donde)) {
      Object.keys(set).forEach(col => {
        hoja.getRange(i + 1, cabecera.indexOf(col) + 1).setValue(set[col]);
      });
      actualizadas++;
    }
  }
  return actualizadas;
}

function _marcarPertenencia(hoja, columnaValor, columnaDestino, pertenece, si, no) {
  const valores = hoja.getDataRange().getValues();
  const cabecera = valores[0];
  const idxValor = cabecera.indexOf(columnaValor);
  let idxDestino = cabecera.indexOf(columnaDestino);
  if (idxDestino === -1) {
    hoja.getRange(1, cabecera.length + 1).setValue(columnaDestino);
    idxDestino = cabecera.length;
  }
  const conjunto = new Set(pertenece);
  let marcadas = 0;
  for (let i = 1; i < valores.length; i++) {
    const esMiembro = conjunto.has(valores[i][idxValor]);
    hoja.getRange(i + 1, idxDestino + 1).setValue(esMiembro ? si : no);
    if (esMiembro) marcadas++;
  }
  return marcadas;
}
