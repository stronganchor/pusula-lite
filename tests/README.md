# Pusula Lite Regression Tests

Run the fast source regression suite from the repo root:

```powershell
.\tests\run-regression-tests.ps1
```

This checks:

- PHP syntax for `pusula-lite-api.php`
- JavaScript syntax for `assets/pusula-app.js`
- route, auth, customer, sale, installment, payment create/delete, lock,
  report, expected-payment, offline snapshot, offline filter, and stale
  navigation source regressions
- `git diff --check`

Run this suite and update it when making plugin behavior changes. In particular,
changes to customer, sale, installment, payment, report, expected-payment,
offline, or navigation behavior should add or adjust regression coverage in the
same commit.

Optional local API integration test:

```powershell
.\tests\local\run-local-api-regression.ps1 `
  -BaseUrl 'http://enes-beko-local.local' `
  -WpPath 'C:\Users\messy\Local Sites\enes-beko-local\app\public\wp-load.php'
```

The local API test covers the main REST workflow: auth, customer create/read/
update/search with contacts, lock acquire/conflict/release, sale create/update/
idempotency, installment create/update/totals, payment create/history/delete,
daily report payment and down-payment amounts, expected payments, offline
snapshot contents, and customer delete cascade cleanup.
