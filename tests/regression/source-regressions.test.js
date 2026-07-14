const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const repoRoot = path.resolve(__dirname, '..', '..');
const apiSource = fs.readFileSync(path.join(repoRoot, 'pusula-lite-api.php'), 'utf8');
const appSource = fs.readFileSync(path.join(repoRoot, 'assets', 'pusula-app.js'), 'utf8');
const exporterSource = fs.readFileSync(path.join(repoRoot, 'tools', 'pusula-desktop-export.php'), 'utf8');

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

function assertMarkersInOrder(source, markers) {
  let cursor = -1;
  markers.forEach((marker) => {
    const index = source.indexOf(marker, cursor + 1);
    assert.notEqual(index, -1, `Missing marker: ${marker}`);
    assert.ok(index > cursor, `Marker is out of order: ${marker}`);
    cursor = index;
  });
}

test('desktop exporter declares the exact ordered import bundle fields', () => {
  const buildBundle = extractBlock(exporterSource, 'public function build_bundle');

  assertMarkersInOrder(buildBundle, [
    "'format_version'",
    "'source'",
    "'source_version'",
    "'exported_at'",
    "'business_profile'",
    "'customers'",
    "'contacts'",
    "'sales'",
    "'installments'",
    "'payments'",
    "'manifest'",
  ]);
  assertMarkersInOrder(extractBlock(exporterSource, 'private function read_customers'), [
    "'id'", "'name'", "'phone'", "'address'", "'work_address'", "'notes'", "'registration_date'",
  ]);
  assertMarkersInOrder(extractBlock(exporterSource, 'private function read_contacts'), [
    "'id'", "'customer_id'", "'name'", "'phone'", "'home_address'", "'work_address'",
  ]);
  assertMarkersInOrder(extractBlock(exporterSource, 'private function read_sales'), [
    "'id'", "'customer_id'", "'date'", "'total_kurus'", "'description'", "'request_key'",
  ]);
  assertMarkersInOrder(extractBlock(exporterSource, 'private function read_installments'), [
    "'id'", "'sale_id'", "'due_date'", "'amount_kurus'", "'paid_date'",
  ]);
  assertMarkersInOrder(extractBlock(exporterSource, 'private function read_payments'), [
    "'id'", "'installment_id'", "'amount_kurus'", "'payment_date'", "'created_at'",
  ]);
});

test('desktop exporter hashes a compact bundle with an empty sha256 field', () => {
  const buildBundle = extractBlock(exporterSource, 'public function build_bundle');
  const encodeJson = extractBlock(exporterSource, 'public function encode_json');

  assert.match(buildBundle, /'sha256'\s*=>\s*''/);
  assert.match(buildBundle, /hash\(\s*'sha256',\s*\$this->encode_json\(\s*\$bundle,\s*false\s*\)\s*\)/);
  assert.match(encodeJson, /JSON_UNESCAPED_SLASHES\s*\|\s*JSON_UNESCAPED_UNICODE/);
  assert.match(exporterSource, /START TRANSACTION WITH CONSISTENT SNAPSHOT/);
  assert.match(exporterSource, /ORDER BY id ASC/);
});

test('desktop exporter is opt-in, excludes unrelated data, and protects output', () => {
  assert.doesNotMatch(apiSource, /pusula-desktop-export\.php/);
  assert.match(exporterSource, /WP_CLI::add_command\(\s*'pusula desktop-export'/);
  assert.match(exporterSource, /\[--dry-run\]/);
  assert.match(exporterSource, /\[--force\]/);
  assert.match(exporterSource, /file_exists\(\s*\$output\s*\)\s*&&\s*!\s*\$force/);
  assert.match(exporterSource, /tempnam\(/);
  assert.doesNotMatch(exporterSource, /read_rows\(\s*'locks'/);
  assert.doesNotMatch(exporterSource, /wp_users|\$wpdb->users|pusula_lite_api_key/);
});

test('REST route map exposes the main plugin surfaces', () => {
  const routes = extractBlock(apiSource, 'public function register_routes');
  const expectedRoutes = [
    "'/customers'",
    "'/customers/next-id'",
    "'/customers/(?P<id>\\d+)'",
    "'/customers/(?P<id>\\d+)/contacts'",
    "'/sales'",
    "'/sales/(?P<id>\\d+)'",
    "'/installments'",
    "'/installments/(?P<id>\\d+)'",
    "'/installments/(?P<id>\\d+)/payments'",
    "'/installments/(?P<id>\\d+)/payments/(?P<payment_id>\\d+)'",
    "'/daily-report'",
    "'/expected-payments'",
    "'/offline-snapshot'",
    "'/locks'",
    "'/locks/release'",
  ];
  const expectedCallbacks = [
    'get_customers',
    'create_customer',
    'get_customer',
    'update_customer',
    'delete_customer',
    'get_contacts',
    'replace_contacts',
    'get_sales',
    'create_sale',
    'get_sale',
    'update_sale',
    'delete_sale',
    'get_installments',
    'create_installment',
    'update_installment',
    'get_installment_payments',
    'create_installment_payment',
    'delete_installment_payment',
    'get_daily_report',
    'get_expected_payments',
    'get_offline_snapshot',
    'acquire_lock',
    'release_lock',
  ];

  expectedRoutes.forEach((route) => assert.ok(routes.includes(route), `Missing route ${route}`));
  expectedCallbacks.forEach((callback) => assert.ok(routes.includes(`'${callback}'`), `Missing callback ${callback}`));
});

test('REST permissions allow pusula users/admins and API key fallback only', () => {
  const permission = extractBlock(apiSource, 'public function permission_callback');

  assert.match(permission, /is_user_logged_in\(\)/);
  assert.match(permission, /in_array\(\s*self::ROLE,\s*\(array\) \$user->roles,\s*true\s*\)/);
  assert.match(permission, /current_user_can\(\s*'manage_options'\s*\)/);
  assert.match(permission, /\$request->get_header\(\s*'x-api-key'\s*\)/);
  assert.match(permission, /hash_equals\(\s*\$stored,\s*\$provided\s*\)/);
  assert.match(permission, /new WP_Error\(\s*'pusula_forbidden'/);
});

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

test('sales API with installments includes payment data and aggregate totals', () => {
  const getSales = extractBlock(apiSource, 'public function get_sales');

  assert.match(getSales, /\$with_inst\s*=\s*\$with && false !== strpos\(\s*\$with,\s*'installments'\s*\)/);
  assert.match(getSales, /enrich_installments_with_payment_data\(\s*\$inst_rows,\s*'id',\s*true\s*\)/);
  assert.match(getSales, /\$row\['installments'\]\s*=\s*\$installments/);
  assert.match(getSales, /\$row\['installments_total'\]/);
  assert.match(getSales, /\$row\['installments_paid_total'\]/);
  assert.match(getSales, /\$row\['installments_remaining_total'\]/);
});

test('customer delete cascades through contacts, sales, installments, and payments', () => {
  const deleteCustomer = extractBlock(apiSource, 'public function delete_customer');

  assert.match(deleteCustomer, /\$wpdb->delete\(\s*\$pay_table,\s*array\(\s*'installment_id'\s*=>\s*\$installment_id\s*\)/);
  assert.match(deleteCustomer, /\$wpdb->delete\(\s*\$inst_table,\s*array\(\s*'sale_id'\s*=>\s*\$sid\s*\)/);
  assert.match(deleteCustomer, /\$wpdb->delete\(\s*\$sales_table,\s*array\(\s*'customer_id'\s*=>\s*\$id\s*\)/);
  assert.match(deleteCustomer, /\$wpdb->delete\(\s*\$contact_tbl,\s*array\(\s*'customer_id'\s*=>\s*\$id\s*\)/);
  assert.match(deleteCustomer, /\$wpdb->delete\(\s*\$cust_table,\s*array\(\s*'id'\s*=>\s*\$id\s*\)/);
});

test('expected payments report keeps unpaid rows and payments completed today', () => {
  const expectedPayments = extractBlock(apiSource, 'private function get_expected_payment_rows');

  assert.match(expectedPayments, /\$today\s*=\s*current_time\(\s*'Y-m-d'\s*\)/);
  assert.match(expectedPayments, /enrich_installments_with_payment_data\(\s*\$rows,\s*'installment_id',\s*false\s*\)/);
  assert.match(expectedPayments, /\$is_paid_today\s*=\s*\$remaining <= 0\.00001 && \$paid_date === \$today/);
  assert.match(expectedPayments, /\$remaining > 0\.00001 \|\| \$is_paid_today/);
  assert.match(expectedPayments, /\$row\['installment_amount'\]\s*=\s*\$this->to_money_float/);
});

test('payment deletion recalculates installment status and returns refreshed payload', () => {
  const deletePayment = extractBlock(apiSource, 'public function delete_installment_payment');

  assert.match(deletePayment, /\$wpdb->delete\(\s*\$pay_table,\s*array\(\s*'id'\s*=>\s*\$payment_id\s*\)/);
  assert.match(deletePayment, /\$this->recalculate_installment_payment_status\(\s*\$id\s*\)/);
  assert.match(deletePayment, /'deleted'\s*=>\s*true/);
  assert.match(deletePayment, /'installment'\s*=>\s*\$this->get_installment_row_with_payments\(\s*\$id,\s*true\s*\)/);
});

test('offline snapshot includes customers, sales with installments, business profile, and expected payments', () => {
  const snapshot = extractBlock(apiSource, 'public function get_offline_snapshot');

  assert.match(snapshot, /get_contacts_for_customers/);
  assert.match(snapshot, /enrich_customers_with_late_flags/);
  assert.match(snapshot, /enrich_customers_with_debt_totals/);
  assert.match(snapshot, /\$sales_request->set_param\(\s*'with',\s*'installments'\s*\)/);
  assert.match(snapshot, /'version'\s*=>\s*self::VERSION/);
  assert.match(snapshot, /'business'\s*=>\s*self::get_business_profile\(\)/);
  assert.match(snapshot, /'customers'\s*=>\s*\$customers/);
  assert.match(snapshot, /'sales'\s*=>\s*\$sales/);
  assert.match(snapshot, /'expected_payments'\s*=>\s*\$this->get_expected_payment_rows\(\)/);
});

test('lock API requires device ids, detects write conflicts, and releases by device', () => {
  const requireDevice = extractBlock(apiSource, 'private function require_device_id');
  const acquireLock = extractBlock(apiSource, 'public function acquire_lock');
  const releaseLock = extractBlock(apiSource, 'public function release_lock');

  assert.match(requireDevice, /\$request->get_header\(\s*'x-device-id'\s*\)/);
  assert.match(requireDevice, /new WP_Error\(\s*'missing_device'/);
  assert.match(acquireLock, /\$this->purge_expired_locks\(\)/);
  assert.match(acquireLock, /mode = 'write' AND device_id <> %s/);
  assert.match(acquireLock, /new WP_Error\(\s*'lock_conflict'/);
  assert.match(acquireLock, /\$wpdb->replace\(/);
  assert.match(releaseLock, /\$this->require_device_id\(\s*\$request\s*\)/);
  assert.match(releaseLock, /'device_id'\s*=>\s*\$device/);
  assert.match(releaseLock, /\$wpdb->delete\(/);
  assert.match(releaseLock, /'released'\s*=>\s*true/);
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

test('offline filters cover customers, sales, daily report, and expected payments', () => {
  const offlineApi = extractBlock(appSource, 'async function offlineApi');

  assert.match(offlineApi, /pathname === '\/customers'/);
  assert.match(offlineApi, /filterOfflineCustomers\(url\.searchParams\)/);
  assert.match(offlineApi, /pathname === '\/sales'/);
  assert.match(offlineApi, /filterOfflineSales\(url\.searchParams\)/);
  assert.match(offlineApi, /pathname === '\/daily-report'/);
  assert.match(offlineApi, /filterOfflineDailyReport\(url\.searchParams\)/);
  assert.match(offlineApi, /pathname === '\/expected-payments'/);
  assert.match(offlineApi, /filterOfflineExpectedPayments\(url\.searchParams\)/);
  assert.match(offlineApi, /^    throw new Error/m);
});

test('sale form can start installments in the sale month', () => {
  const renderSaleTab = extractBlock(appSource, 'function renderSaleTab');
  const saveSale = extractBlock(appSource, 'async function saveSale');
  const updateSalePreview = extractBlock(appSource, 'function updateSalePreview');
  const dueDateHelper = extractBlock(appSource, 'function calculateInstallmentDueDate');

  assert.match(renderSaleTab, /id="sale-first-month"/);
  assert.match(renderSaleTab, /<option value="1" selected>/);
  assert.match(renderSaleTab, /<option value="0">/);
  assert.match(renderSaleTab, /\['sale-date','sale-total','sale-down','sale-n','sale-due','sale-first-month'\]/);
  assert.match(saveSale, /parseFirstDueMonthOffset\(document\.getElementById\('sale-first-month'\)\?\.value \|\| '1'\)/);
  assert.match(saveSale, /calculateInstallmentDueDate\(saleBase,\s*dueDay,\s*i,\s*firstDueMonthOffset\)/);
  assert.match(updateSalePreview, /parseFirstDueMonthOffset\(firstMonthEl\?\.value \|\| '1'\)/);
  assert.match(updateSalePreview, /calculateInstallmentDueDate\(base,\s*dueDay,\s*nInst,\s*firstDueMonthOffset\)/);
  assert.match(dueDateHelper, /saleBase\.getMonth\(\) \+ monthOffset \+ Math\.trunc\(installmentIndex\) - 1/);
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

test('customer info tab refills after selecting a different customer from search', () => {
  const activateTab = extractBlock(appSource, 'function activateTab');
  const addTabBranch = sliceBetween(
    activateTab,
    "if (tabName === 'add') {",
    "if (tabName === 'sale') {"
  );
  const fillCustomerForm = extractBlock(appSource, 'function fillCustomerForm');

  assert.match(addTabBranch, /const selectedId\s*=\s*customerIdOf\(state\.selected\);/);
  assert.match(addTabBranch, /const formMatchesSelected\s*=\s*selectedId && state\.addFormCustomerId === selectedId;/);
  assert.match(addTabBranch, /if \(!formMatchesSelected \|\| !isAddFormDirty\(\)\) fillCustomerForm\(state\.selected\);/);
  assert.match(fillCustomerForm, /state\.addFormCustomerId\s*=\s*null;/);
  assert.match(fillCustomerForm, /state\.addFormCustomerId\s*=\s*customerIdOf\(cust\);/);
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
