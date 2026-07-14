$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
    php -l pusula-lite-api.php
    php -l tools\pusula-desktop-export.php
    php -l tests\php\exporter.test.php
    php tests\php\exporter.test.php
    node --check assets\pusula-app.js
    node --test tests\regression\source-regressions.test.js
    git diff --check
} finally {
    Pop-Location
}
