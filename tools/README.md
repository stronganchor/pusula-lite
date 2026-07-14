# Pusula Desktop Legacy Export

`pusula-desktop-export.php` is an opt-in WP-CLI command for the one-time move
from Pusula Lite on WordPress to Pusula Desktop. The plugin does not load this
file during normal requests, so it does not add REST routes or change live app
behavior.

The export contains only the business profile and the Pusula customer, contact,
sale, installment, and installment-payment records. It excludes locks, API
keys, credentials, WordPress users, and unrelated WordPress tables.

## Before exporting

1. Take and verify a WordPress/database backup.
2. Put the Pusula Lite interface into the planned cutover freeze so records do
   not change after the final export.
3. Choose an explicit output path outside the web root and repository. The JSON
   contains customer and financial data and must be handled as sensitive data.
4. Run the dry-run first. It reads a consistent snapshot, validates IDs and all
   relationships, and prints only counts, financial totals in kuruş, and the
   checksum. It writes no file.

Run the command on the WordPress host from this plugin repository, with
`--path` pointing to the WordPress installation. For a Linux host:

```bash
wp --path=/home/account/public_html --require=tools/pusula-desktop-export.php pusula desktop-export \
  --output=/home/account/private/pusula-desktop-export.json \
  --dry-run
```

For a local Windows WordPress installation:

```powershell
wp --path='C:\path\to\wordpress' --require=tools/pusula-desktop-export.php pusula desktop-export `
  --output='C:\secure\pusula-desktop-export.json' `
  --dry-run
```

Create the bundle only after reviewing the dry-run summary:

```powershell
wp --path='C:\path\to\wordpress' --require=tools/pusula-desktop-export.php pusula desktop-export `
  --output='C:\secure\pusula-desktop-export.json'
```

An existing output file is never replaced unless `--force` is supplied. The
command writes a complete temporary file in the destination directory and then
renames it into place, so a validation or write failure does not leave a partial
bundle at the requested path.

## Bundle contract

- `format_version` is `1`, `source` is `pusula-lite-wordpress`, and
  `source_version` is the active plugin's `Pusula_Lite_API::VERSION`.
- `exported_at` is UTC RFC3339 (`YYYY-MM-DDTHH:MM:SSZ`).
- Records are ordered by ascending source ID, and original IDs and relationships
  are preserved.
- MySQL `DECIMAL` values are parsed as strings and converted exactly to integer
  kuruş without floating-point arithmetic.
- The manifest contains record counts, sales/installment/payment totals in
  kuruş, and a lowercase SHA-256 checksum.
- To calculate the checksum, set `manifest.sha256` to an empty string and encode
  the full ordered bundle as compact UTF-8 JSON with Unicode, slashes, and line
  terminators unescaped. SHA-256 those exact bytes, then place the hex digest in
  `manifest.sha256`. The saved handoff file is pretty-printed UTF-8 JSON.

After importing, compare the desktop import summary with the dry-run/export
counts, totals, and checksum. Retain the WordPress backup and export according
to the migration runbook; do not commit customer exports to Git.
