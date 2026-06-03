param(
    [string] $BaseUrl = 'http://enes-beko-local.local',
    [string] $ApiKey = '',
    [string] $WpPath = ''
)

$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-ApiKeyFromWordPress {
    param([string] $Path)

    Assert-True ($Path -and (Test-Path -LiteralPath $Path)) "WpPath was not found: $Path"

    $tempFile = Join-Path ([System.IO.Path]::GetTempPath()) ("pusula-api-key-{0}.php" -f ([guid]::NewGuid().ToString('N')))
    try {
        @"
<?php
require '$($Path.Replace('\', '/'))';
echo get_option('pusula_lite_api_key');
"@ | Set-Content -LiteralPath $tempFile -Encoding UTF8

        $key = (& php $tempFile)
        return [string] $key
    } finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
}

if (-not $ApiKey) {
    if (-not $WpPath) {
        throw 'Provide -ApiKey or -WpPath so the local REST API can be authenticated.'
    }
    $ApiKey = Get-ApiKeyFromWordPress -Path $WpPath
}

Assert-True ($ApiKey.Length -gt 0) 'API key is empty.'

$base = $BaseUrl.TrimEnd('/')
$apiBase = "$base/wp-json/pusula/v1"
$headers = @{ 'x-api-key' = $ApiKey }
$customerId = $null

function Invoke-PusulaApi {
    param(
        [ValidateSet('GET', 'POST', 'PUT', 'DELETE')] [string] $Method,
        [string] $Path,
        [object] $Body = $null
    )

    $uri = "$apiBase$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
    }

    $json = $Body | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType 'application/json' -Body $json
}

try {
    $today = Get-Date -Format 'yyyy-MM-dd'
    $yesterday = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
    $stamp = Get-Date -Format 'yyyyMMddHHmmss'
    $marker = "Codex API regression $stamp"
    $paymentAmount = 123.45
    $saleTotal = 1000.00

    $customer = Invoke-PusulaApi -Method POST -Path '/customers' -Body @{
        name = $marker
        phone = '555000REG'
        address = 'Temporary regression customer'
        work_address = ''
        notes = $marker
        registration_date = $today
        contacts = @()
    }
    $customerId = [int] $customer.id
    Assert-True ($customerId -gt 0) 'Customer creation did not return an id.'

    $sale = Invoke-PusulaApi -Method POST -Path '/sales' -Body @{
        customer_id = $customerId
        date = $yesterday
        total = $saleTotal
        description = $marker
        request_key = "codex-regression-$stamp"
    }
    $saleId = [int] $sale.id
    Assert-True ($saleId -gt 0) 'Sale creation did not return an id.'

    $installment = Invoke-PusulaApi -Method POST -Path '/installments' -Body @{
        sale_id = $saleId
        due_date = $today
        amount = $saleTotal
        paid = 0
    }
    $installmentId = [int] $installment.id
    Assert-True ($installmentId -gt 0) 'Installment creation did not return an id.'

    $payment = Invoke-PusulaApi -Method POST -Path "/installments/$installmentId/payments" -Body @{
        amount = $paymentAmount
        payment_date = $today
    }
    $paymentId = [int] $payment.payment.id
    Assert-True ($paymentId -gt 0) 'Payment creation did not return an id.'

    $report = @(Invoke-PusulaApi -Method GET -Path "/daily-report?start=$today&end=$today")
    $matches = @($report | Where-Object {
        $_.event_type -eq 'installment_payment' -and
        [string] $_.payment_id -eq [string] $paymentId -and
        [string] $_.sale_id -eq [string] $saleId
    })

    Assert-True ($matches.Count -eq 1) "Expected one matching daily report payment row; found $($matches.Count)."
    $row = $matches[0]

    Assert-True ([math]::Abs(([double] $row.total) - $paymentAmount) -lt 0.001) "Daily report total was $($row.total), expected $paymentAmount."
    Assert-True ([math]::Abs(([double] $row.amount) - $paymentAmount) -lt 0.001) "Daily report amount was $($row.amount), expected $paymentAmount."
    Assert-True ([math]::Abs(([double] $row.sale_total) - $saleTotal) -lt 0.001) "Daily report sale_total was $($row.sale_total), expected $saleTotal."
    Assert-True ([math]::Abs(([double] $row.total) - $saleTotal) -gt 0.001) 'Daily report total regressed to the full sale total.'

    [pscustomobject] @{
        passed = $true
        customer_id = $customerId
        sale_id = $saleId
        installment_id = $installmentId
        payment_id = $paymentId
        report_total = $row.total
        report_sale_total = $row.sale_total
    } | ConvertTo-Json -Depth 5
} finally {
    if ($customerId) {
        try {
            Invoke-PusulaApi -Method DELETE -Path "/customers/$customerId" | Out-Null
        } catch {
            Write-Warning "Could not delete temporary customer ${customerId}: $($_.Exception.Message)"
        }
    }
}
