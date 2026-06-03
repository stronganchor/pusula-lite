# Pusula Lite Regression Tests

Run the fast source regression suite from the repo root:

```powershell
.\tests\run-regression-tests.ps1
```

This checks:

- PHP syntax for `pusula-lite-api.php`
- JavaScript syntax for `assets/pusula-app.js`
- source regressions for daily report payment amounts
- source regressions for stale customer navigation selection
- `git diff --check`

Optional local API integration test:

```powershell
.\tests\local\run-local-api-regression.ps1 `
  -BaseUrl 'http://enes-beko-local.local' `
  -WpPath 'C:\Users\messy\Local Sites\enes-beko-local\app\public\wp-load.php'
```

The local API test creates a temporary customer, sale, installment, and payment,
verifies the daily report uses the payment amount rather than the full sale
amount, then deletes the temporary customer.
