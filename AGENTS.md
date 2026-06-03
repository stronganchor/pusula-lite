# Pusula Lite Local Instructions

## Regression Tests

- Run `.\tests\run-regression-tests.ps1` before committing code changes.
- When a change affects customer, sale, installment, payment, report, expected-payment, offline, or navigation behavior, update the regression tests in `tests/` in the same change.
- For changes that touch REST API behavior, also run the LocalWP integration test when the local Enes Beko site is available:

```powershell
.\tests\local\run-local-api-regression.ps1 `
  -BaseUrl 'http://enes-beko-local.local' `
  -WpPath 'C:\Users\messy\Local Sites\enes-beko-local\app\public\wp-load.php'
```

- Keep local integration tests self-cleaning. Temporary customers, sales, installments, and payments must be removed at the end of each run.
