/**
 * Endpoint de escritura para los Atajos de iOS y la web (web/).
 *
 * Despliegue: Extensiones > Apps Script > Implementar > Nueva implementación
 *   Tipo: Aplicación web | Ejecutar como: yo | Acceso: cualquiera con el enlace
 *
 * El acceso "cualquiera con el enlace" es obligatorio para que el Atajo y la
 * web puedan llamarlo, por eso el token es la única protección real. Que sea
 * largo. Se comprueba en cada petición vía `_autorizado()` (ver doGet.gs).
 *
 * El token NO va en este archivo (se commitea a git). Se guarda en
 * Project Settings > Script Properties, clave TOKEN. Ejecutar una vez
 * `configurarToken()` desde el editor (con el valor real puesto ahí
 * temporalmente) y borrar el valor del código después, o pegarlo
 * directamente en la UI de Script Properties.
 *
 * `accion` (default "append", así el Atajo de iPhone —que nunca manda este
 * campo— sigue funcionando igual que antes):
 *   - "append": añade cada fila de `filas` al final. Igual que siempre.
 *   - "delete_where": borra las filas donde todas las columnas de `donde`
 *     coincidan (columna: valor).
 *   - "update_where": en las filas que coincidan con `donde`, escribe cada
 *     columna:valor de `set` — crea la columna al final si `set` trae una
 *     que todavía no existe en la pestaña (igual que marcar_pertenencia).
 *   - "marcar_pertenencia": para cada fila, mira `valores[columna_valor]` y
 *     escribe en `columna_destino` el valor `si` si está en la lista
 *     `pertenece`, o `no` si no — pensado para
 *     actualizar_titulares_mi_plantilla (marca todo el once de una vez).
 */

function configurarToken() {
  // Pegar aquí el token SOLO para ejecutar esta función una vez, luego borrar.
  PropertiesService.getScriptProperties().setProperty('TOKEN', 'PEGAR_AQUI_Y_BORRAR_DESPUES');
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (!_autorizado(data.token)) {
      return _json({ ok: false, error: 'auth' });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const hoja = ss.getSheetByName(data.pestana);
    if (!hoja) throw new Error('pestaña no encontrada: ' + data.pestana);

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

    throw new Error('acción desconocida: ' + accion);

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
  // De abajo a arriba: borrar una fila no desplaza las que faltan por mirar.
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
  // Si `set` trae una columna que la pestaña todavía no tiene, se crea al
  // final antes de escribir filas — si no, la escritura se perdía en
  // silencio (idx === -1, no había rama de error).
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
