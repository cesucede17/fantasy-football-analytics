/**
 * Read endpoint for the web dashboard (web/). Same Apps Script project as
 * doPost.gs, same TOKEN (Project Settings > Script Properties). Needs a
 * fresh "Deploy > New deployment" after pasting this in — Apps Script
 * doesn't redeploy on save alone.
 *
 * `_autorizado()` and `_json()` are helpers shared with doPost.gs.
 *
 * Query params:
 *   ?token=...                                   (always required)
 *   ?todo=1                                       -> every tab at once
 *       (except precios_diarios's full history, which can run to tens of
 *       thousands of rows in a season — instead, only the most recent
 *       day's snapshot is returned, in `snapshot`).
 *   ?todo=1&hojas=mi_plantilla,estado_forma       -> like ?todo=1 but only
 *       those tabs (+ snapshot, always included unless &snapshot=0) — each
 *       page requests only what it uses, instead of all 10 tabs every
 *       time; less data read and less JSON to send.
 *   ?hoja=NAME                                   -> that whole tab.
 *   ?hoja=precios_diarios&jugador_id=X            -> one player's history
 *       (for the price chart).
 *   ?accion=valor_historico&jugador_id=X&fecha=YYYY-MM-DD
 *       -> that player's market value on that day, fetched live from
 *       futbolfantasy.com's 30-day history (a port of
 *       scraper_precios.valor_historico_jugador — the browser can't call
 *       that site directly due to CORS, but Apps Script can).
 */

const PESTANAS_TODO = [
  'mi_plantilla', 'watchlist', 'mercado_diario', 'movimientos_liga',
  'plantillas_rivales', 'config', 'estado_jugadores', 'estado_forma',
  'calendario_resultados', 'clasificacion_anterior', 'puntos_jornada',
  'pool_puntos',
];

function doGet(e) {
  try {
    if (!_autorizado(e.parameter.token)) {
      return _json({ ok: false, error: 'auth' });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();

    if (e.parameter.accion === 'valor_historico') {
      return _json({ ok: true, valor: _valorHistorico(e.parameter.jugador_id, e.parameter.fecha) });
    }

    if (e.parameter.hoja === 'precios_diarios' && e.parameter.jugador_id) {
      const historico = _leerHojaSegura(ss, 'precios_diarios')
        .filter(f => String(f.jugador_id) === String(e.parameter.jugador_id));
      return _json({ ok: true, filas: historico });
    }

    if (e.parameter.hoja) {
      return _json({ ok: true, filas: _leerHojaSegura(ss, e.parameter.hoja) });
    }

    // !== undefined, not truthy: ?hojas= (empty, "no extra tabs, just the
    // snapshot") is a valid value, distinct from "hojas= wasn't sent at all".
    const pedidas = e.parameter.hojas !== undefined
      ? PESTANAS_TODO.filter(p => e.parameter.hojas.split(',').includes(p))
      : PESTANAS_TODO;

    const datos = {};
    pedidas.forEach(nombre => { datos[nombre] = _leerHojaSegura(ss, nombre); });
    // config is a single row of settings, not a list — flattened into a
    // plain object so the client can read datos.config.saldo directly.
    if ('config' in datos) datos.config = datos.config[0] || {};
    if (e.parameter.snapshot !== '0') datos.snapshot = _snapshotMasReciente(ss);
    return _json({ ok: true, datos });

  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function _autorizado(token) {
  const TOKEN = PropertiesService.getScriptProperties().getProperty('TOKEN');
  return Boolean(TOKEN) && token === TOKEN;
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function _valorCelda(valor) {
  // Sheets auto-detects any "2026-09-03"-shaped text written with
  // USER_ENTERED (how the scrapers write) as a date — SpreadsheetApp.getValues()
  // then returns those cells as a Date object (with time and timezone),
  // unlike gspread in Python, which returns the string as-is. Normalized
  // here to "YYYY-MM-DD" so the web dashboard sees the same thing Python
  // always saw.
  if (Object.prototype.toString.call(valor) === '[object Date]') {
    return Utilities.formatDate(valor, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  return valor;
}

function _leerHoja(ss, nombre) {
  const hoja = ss.getSheetByName(nombre);
  if (!hoja) throw new Error('tab not found: ' + nombre);
  const valores = hoja.getDataRange().getValues();
  const cabecera = valores[0];
  return valores.slice(1).map(fila => {
    const obj = {};
    cabecera.forEach((col, i) => { obj[col] = _valorCelda(fila[i]); });
    return obj;
  });
}

function _leerHojaSegura(ss, nombre) {
  try {
    return _leerHoja(ss, nombre);
  } catch (err) {
    return []; // a new tab that doesn't exist yet (e.g. before the first backfill)
  }
}

function _snapshotMasReciente(ss) {
  // precios_diarios keeps growing (a ~700-row block every day) and
  // _leerHoja reads the entire tab — after a few months of season this
  // becomes by far the slowest part of ?todo=1. A single day's snapshot is
  // always at the end (daily append), so reading just the tail of the
  // sheet is enough instead of the whole history.
  const hoja = ss.getSheetByName('precios_diarios');
  if (!hoja) return [];
  const ultimaFila = hoja.getLastRow();
  if (ultimaFila < 2) return [];

  const MARGEN_FILAS = 1500; // ~2x the pool size (~700 players), ample margin
  const inicio = Math.max(2, ultimaFila - MARGEN_FILAS + 1);
  const cabecera = hoja.getRange(1, 1, 1, hoja.getLastColumn()).getValues()[0];
  const valores = hoja.getRange(inicio, 1, ultimaFila - inicio + 1, cabecera.length).getValues();
  const filas = valores.map(fila => {
    const obj = {};
    cabecera.forEach((col, i) => { obj[col] = _valorCelda(fila[i]); });
    return obj;
  });

  const fechaMax = filas.reduce((max, f) => (f.fecha > max ? f.fecha : max), filas[0].fecha);
  return filas.filter(f => f.fecha === fechaMax);
}

function _valorHistorico(jugadorId, fechaIso) {
  const url = 'https://www.futbolfantasy.com/analytics/laliga-fantasy/mercado/detalle/' + jugadorId + '?perfil=1';
  const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) return null;
  const texto = resp.getContentText();

  const fecha = new Date(fechaIso + 'T00:00:00');
  const dd = ('0' + fecha.getDate()).slice(-2);
  const mm = ('0' + (fecha.getMonth() + 1)).slice(-2);
  const patron = new RegExp('player_chartjs_30\\.push\\(\\{date:\\s*"' + dd + '/' + mm + '",\\s*value:\\s*(\\d+)\\}\\)');
  const m = texto.match(patron);
  return m ? parseInt(m[1], 10) : null;
}
