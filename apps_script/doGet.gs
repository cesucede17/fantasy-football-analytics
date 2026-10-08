/**
 * Endpoint de lectura para la web (web/). Mismo proyecto de Apps Script que
 * doPost.gs, mismo TOKEN (Project Settings > Script Properties). Hace falta
 * volver a "Implementar > Nueva implementación" después de pegar esto —
 * Apps Script no redespliega solo al guardar.
 *
 * `_autorizado()` y `_json()` son helpers compartidos con doPost.gs.
 *
 * Query params:
 *   ?token=...                                   (siempre obligatorio)
 *   ?todo=1                                       -> todas las pestañas de
 *       una vez (menos el histórico completo de precios_diarios, que puede
 *       tener decenas de miles de filas en una temporada — en su lugar se
 *       devuelve solo el snapshot del día más reciente, en `snapshot`).
 *   ?todo=1&hojas=mi_plantilla,estado_forma       -> como ?todo=1 pero solo
 *       esas pestañas (+ snapshot, que siempre se incluye salvo
 *       &snapshot=0) — cada página pide solo lo que usa, en vez de las 10
 *       pestañas siempre; menos datos leídos y menos JSON que mandar.
 *   ?hoja=NOMBRE                                   -> esa pestaña entera.
 *   ?hoja=precios_diarios&jugador_id=X             -> histórico de un jugador
 *       (para la gráfica de precio).
 *   ?accion=valor_historico&jugador_id=X&fecha=YYYY-MM-DD
 *       -> valor de mercado de ese jugador ese día, sacado en vivo del
 *       histórico de 30 días de futbolfantasy.com (puerto de
 *       scraper_precios.valor_historico_jugador — el navegador no puede
 *       llamar a ese sitio por CORS, Apps Script sí).
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

    // !== undefined, no truthy: ?hojas= (vacío, "ninguna pestaña extra,
    // solo snapshot") es un valor válido y distinto de "no venía hojas=".
    const pedidas = e.parameter.hojas !== undefined
      ? PESTANAS_TODO.filter(p => e.parameter.hojas.split(',').includes(p))
      : PESTANAS_TODO;

    const datos = {};
    pedidas.forEach(nombre => { datos[nombre] = _leerHojaSegura(ss, nombre); });
    // config es una sola fila de ajustes, no una lista — se aplana a objeto
    // plano para que el cliente lea datos.config.saldo directamente.
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
  // Sheets auto-detecta como fecha cualquier texto tipo "2026-09-03" escrito
  // con USER_ENTERED (así escriben los scrapers) — SpreadsheetApp.getValues()
  // devuelve esas celdas como objeto Date (con hora y huso horario), a
  // diferencia de gspread en Python, que da el string tal cual. Se normaliza
  // aquí a "YYYY-MM-DD" para que la web vea lo mismo que siempre vio Python.
  if (Object.prototype.toString.call(valor) === '[object Date]') {
    return Utilities.formatDate(valor, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  return valor;
}

function _leerHoja(ss, nombre) {
  const hoja = ss.getSheetByName(nombre);
  if (!hoja) throw new Error('pestaña no encontrada: ' + nombre);
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
    return []; // pestaña nueva que todavía no existe (p.ej. antes del primer backfill)
  }
}

function _snapshotMasReciente(ss) {
  // precios_diarios crece sin parar (un bloque de ~700 filas cada día) y
  // _leerHoja lee la pestaña entera — con unos meses de temporada esto se
  // vuelve la parte más lenta, con diferencia, de ?todo=1. El snapshot de
  // un solo día siempre está al final (append diario), así que basta con
  // leer la cola de la hoja en vez de todo el histórico.
  const hoja = ss.getSheetByName('precios_diarios');
  if (!hoja) return [];
  const ultimaFila = hoja.getLastRow();
  if (ultimaFila < 2) return [];

  const MARGEN_FILAS = 1500; // ~2x el pool (~700 jugadores), margen de sobra
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
