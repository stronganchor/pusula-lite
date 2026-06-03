const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repoRoot = path.resolve(__dirname, '..', '..');
const apiSource = fs.readFileSync(path.join(repoRoot, 'pusula-lite-api.php'), 'utf8');
const appSource = fs.readFileSync(path.join(repoRoot, 'assets', 'pusula-app.js'), 'utf8');

function extractBlock(source, marker) {
  const markerIndex = source.indexOf(marker);
  assert.notEqual(markerIndex, -1, `Missing marker: ${marker}`);

  const openIndex = source.indexOf('{', markerIndex);
  assert.notEqual(openIndex, -1, `Missing opening brace after marker: ${marker}`);

  let depth = 0;
  for (let i = openIndex; i < source.length; i += 1) {
    const char = source[i];
    if (char === '{') depth += 1;
    if (char === '}') depth -= 1;
    if (depth === 0) {
      return source.slice(markerIndex, i + 1);
    }
  }

  assert.fail(`Missing closing brace after marker: ${marker}`);
}

function sliceBetween(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  assert.notEqual(start, -1, `Missing start marker: ${startMarker}`);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(end, -1, `Missing end marker: ${endMarker}`);
  return source.slice(start, end);
}

test('daily report API uses installment payment amount, not sale total', () => {
  const dailyReport = extractBlock(apiSource, 'private function get_daily_report_rows');

  assert.match(
    dailyReport,
    /\$payment_amount\s*=\s*\$this->to_money_float\(\s*\$payment_row\['amount'\]\s*\)\s*;/,
    'payment rows must derive the report amount from p.amount'
  );
  assert.match(dailyReport, /'event_type'\s*=>\s*'installment_payment'/);
  assert.match(dailyReport, /'total'\s*=>\s*\$payment_amount/);
  assert.match(dailyReport, /'amount'\s*=>\s*\$payment_amount/);
  assert.match(
    dailyReport,
    /'sale_total'\s*=>\s*\$this->to_money_float\(\s*\$payment_row\['sale_total'\]\s*\)/,
    'sale total should remain informational and separate from the paid amount'
  );
});

test('offline daily report shim uses installment payment amount', () => {
  const offlineDailyReport = extractBlock(appSource, 'function filterOfflineDailyReport');
  const paymentObject = sliceBetween(
    offlineDailyReport,
    "event_type: 'installment_payment'",
    'description: sale.description'
  );

  assert.match(offlineDailyReport, /const amount\s*=\s*moneyNumber\(payment\.amount\);/);
  assert.match(paymentObject, /total:\s*amount\b/);
  assert.match(paymentObject, /\bamount,\s/);
  assert.match(paymentObject, /sale_total:\s*moneyNumber\(sale\.total\)/);
});

test('customer table rerender does not passively replace selected customer', () => {
  const renderTable = extractBlock(appSource, 'function renderTable');

  assert.doesNotMatch(renderTable, /state\.selected\s*=\s*r\b/);
  assert.equal((renderTable.match(/setSelectedCustomer\(r\)/g) || []).length, 2);

  const selectedRowBlock = sliceBetween(renderTable, 'if (isSelected) {', 'tbody.appendChild(tr);');
  assert.doesNotMatch(selectedRowBlock, /state\.selected\s*=/);
  assert.doesNotMatch(selectedRowBlock, /setSelectedCustomer/);
});

test('main-page customer-info navigation ignores stale selected-customer fetches', () => {
  const renderSearchTab = extractBlock(appSource, 'function renderSearchTab');
  const editHandler = sliceBetween(
    renderSearchTab,
    "document.getElementById('nav-edit').addEventListener",
    "document.getElementById('nav-sale').addEventListener"
  );

  assert.match(editHandler, /const selected\s*=\s*selectedCustomerSnapshot\(\);/);
  assert.match(editHandler, /const selectedId\s*=\s*customerIdOf\(selected\);/);
  assert.match(editHandler, /const selectionSeq\s*=\s*state\.selectionSeq;/);
  assert.match(editHandler, /fetchCustomerById\(selectedId\)/);
  assert.equal((editHandler.match(/isSelectedCustomerStillCurrent\(selectedId,\s*selectionSeq\)/g) || []).length, 2);
  assert.match(editHandler, /activateTab\('add'\)/);
});

test('detail sales responses are ignored after customer selection changes', () => {
  const loadSales = extractBlock(appSource, 'async function loadSales');

  assert.match(loadSales, /const selectedId\s*=\s*String\(customerId\s*\|\|\s*''\)\.trim\(\);/);
  assert.match(loadSales, /const seq\s*=\s*\+\+state\.salesLoadSeq;/);
  assert.equal((loadSales.match(/seq !== state\.salesLoadSeq/g) || []).length, 2);
  assert.equal((loadSales.match(/customerIdOf\(state\.selected\) !== selectedId/g) || []).length, 2);
});

test('selected customer writes go through the selection helper', () => {
  const helper = extractBlock(appSource, 'function setSelectedCustomer');
  const helperStart = appSource.indexOf(helper);
  const helperEnd = helperStart + helper.length;
  const assignments = [...appSource.matchAll(/state\.selected\s*=/g)];

  assert.equal(assignments.length, 1);
  assert.ok(
    assignments.every((match) => match.index >= helperStart && match.index < helperEnd),
    'state.selected should only be assigned inside setSelectedCustomer'
  );
});
