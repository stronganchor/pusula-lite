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

function Assert-Near {
    param(
        [double] $Actual,
        [double] $Expected,
        [string] $Message
    )

    Assert-True ([math]::Abs($Actual - $Expected) -lt 0.001) "$Message Actual=$Actual Expected=$Expected"
}

function ConvertTo-List {
    param([object] $Value)

    if ($null -eq $Value) {
        return @()
    }

    if ($Value -is [array]) {
        if ($Value.Count -eq 1) {
            $props = @($Value[0].PSObject.Properties.Name)
            if ($props -contains 'value' -and $props -contains 'Count') {
                return $Value[0].value
            }
        }
        return $Value
    }

    $propertyNames = @($Value.PSObject.Properties.Name)
    if ($propertyNames -contains 'value' -and $propertyNames -contains 'Count') {
        return $Value.value
    }

    return @($Value)
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

function Invoke-PusulaApiStatus {
    param(
        [ValidateSet('GET', 'POST', 'PUT', 'DELETE')] [string] $Method,
        [string] $Path,
        [hashtable] $Headers = @{},
        [object] $Body = $null
    )

    $uri = "$apiBase$Path"
    $params = @{
        Method = $Method
        Uri = $uri
        Headers = $Headers
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $params.ContentType = 'application/json'
        $params.Body = ($Body | ConvertTo-Json -Depth 10)
    }

    try {
        $response = Invoke-WebRequest @params
        $body = $null
        if ($response.Content) {
            try {
                $body = $response.Content | ConvertFrom-Json
            } catch {
                $body = $response.Content
            }
        }
        [pscustomobject] @{
            StatusCode = [int] $response.StatusCode
            Body = $body
        }
    } catch {
        $response = $_.Exception.Response
        if (-not $response) {
            throw
        }
        $body = $null
        try {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            $content = $reader.ReadToEnd()
            if ($content) {
                try {
                    $body = $content | ConvertFrom-Json
                } catch {
                    $body = $content
                }
            }
        } catch {
            $body = $null
        }
        [pscustomobject] @{
            StatusCode = [int] $response.StatusCode
            Body = $body
        }
    }
}

try {
    $today = Get-Date -Format 'yyyy-MM-dd'
    $tomorrow = (Get-Date).AddDays(1).ToString('yyyy-MM-dd')
    $stamp = Get-Date -Format 'yyyyMMddHHmmss'
    $marker = "Codex full regression $stamp"
    $updatedMarker = "$marker updated"
    $paymentAmount = 123.45
    $saleTotal = 1000.00
    $installmentAmount = 700.00
    $downPayment = 225.00
    $remainingAfterPayment = 576.55

    $unauthorized = Invoke-PusulaApiStatus -Method GET -Path '/customers'
    Assert-True ($unauthorized.StatusCode -eq 401) "Unauthenticated customers request returned $($unauthorized.StatusCode), expected 401."

    $customer = Invoke-PusulaApi -Method POST -Path '/customers' -Body @{
        name = $marker
        phone = '555000REG'
        address = 'Temporary regression customer'
        work_address = 'Temporary regression workplace'
        notes = $marker
        registration_date = $today
        contacts = @(
            @{
                name = 'Regression Contact 1'
                phone = '555000C1'
                home_address = 'Contact home 1'
                work_address = 'Contact work 1'
            },
            @{
                name = 'Regression Contact 2'
                phone = '555000C2'
                home_address = 'Contact home 2'
                work_address = 'Contact work 2'
            }
        )
    }
    $customerId = [int] $customer.id
    Assert-True ($customerId -gt 0) 'Customer creation did not return an id.'

    $customerRow = Invoke-PusulaApi -Method GET -Path "/customers/$customerId"
    Assert-True ($customerRow.name -eq $marker) 'Customer detail returned the wrong name.'
    Assert-True (@(ConvertTo-List $customerRow.contacts).Count -eq 2) 'Customer contacts were not stored.'

    $searchRows = @(ConvertTo-List (Invoke-PusulaApi -Method GET -Path "/customers?name=$([uri]::EscapeDataString($marker))&with=contacts"))
    Assert-True (@($searchRows | Where-Object { [string] $_.id -eq [string] $customerId }).Count -eq 1) 'Customer search did not find the created customer.'

    Invoke-PusulaApi -Method PUT -Path "/customers/$customerId" -Body @{
        name = $updatedMarker
        phone = '555000UPD'
        address = 'Updated regression customer'
        work_address = 'Updated regression workplace'
        notes = $updatedMarker
        registration_date = $today
        contacts = @(
            @{
                name = 'Updated Contact'
                phone = '555000CU'
                home_address = 'Updated contact home'
                work_address = 'Updated contact work'
            }
        )
    } | Out-Null

    $updatedCustomer = Invoke-PusulaApi -Method GET -Path "/customers/$customerId"
    Assert-True ($updatedCustomer.name -eq $updatedMarker) 'Customer update did not persist the new name.'
    Assert-True (@(ConvertTo-List $updatedCustomer.contacts).Count -eq 1) 'Customer update did not replace contacts.'

    $saleRequestKey = "codex-full-regression-$stamp"
    $sale = Invoke-PusulaApi -Method POST -Path '/sales' -Body @{
        customer_id = $customerId
        date = $today
        total = $saleTotal
        description = $marker
        request_key = $saleRequestKey
    }
    $saleId = [int] $sale.id
    Assert-True ($saleId -gt 0) 'Sale creation did not return an id.'

    $sameSale = Invoke-PusulaApi -Method POST -Path '/sales' -Body @{
        customer_id = $customerId
        date = $today
        total = $saleTotal
        description = "$marker duplicate"
        request_key = $saleRequestKey
    }
    Assert-True ([int] $sameSale.id -eq $saleId) 'Sale request_key idempotency returned a different sale id.'

    $saleUpdateDescription = "$marker sale updated"
    Invoke-PusulaApi -Method PUT -Path "/sales/$saleId" -Body @{
        date = $today
        total = $saleTotal
        description = $saleUpdateDescription
    } | Out-Null

    $installment = Invoke-PusulaApi -Method POST -Path '/installments' -Body @{
        sale_id = $saleId
        due_date = $today
        amount = $installmentAmount
        paid = 0
    }
    $installmentId = [int] $installment.id
    Assert-True ($installmentId -gt 0) 'Installment creation did not return an id.'

    $futureInstallment = Invoke-PusulaApi -Method POST -Path '/installments' -Body @{
        sale_id = $saleId
        due_date = $tomorrow
        amount = 50.00
        paid = 0
    }
    $futureInstallmentId = [int] $futureInstallment.id
    Assert-True ($futureInstallmentId -gt 0) 'Future installment creation did not return an id.'

    Invoke-PusulaApi -Method PUT -Path "/installments/$futureInstallmentId" -Body @{
        due_date = $tomorrow
        amount = 75.00
    } | Out-Null

    $payment = Invoke-PusulaApi -Method POST -Path "/installments/$installmentId/payments" -Body @{
        amount = $paymentAmount
        payment_date = $today
    }
    $paymentId = [int] $payment.payment.id
    Assert-True ($paymentId -gt 0) 'Payment creation did not return an id.'
    Assert-Near ([double] $payment.payment.remaining_after_payment) $remainingAfterPayment 'Payment remaining amount was wrong.'

    $installmentPayments = Invoke-PusulaApi -Method GET -Path "/installments/$installmentId/payments"
    $paymentHistoryRows = @(ConvertTo-List $installmentPayments.payments)
    Assert-True (@($paymentHistoryRows | Where-Object { [string] $_.id -eq [string] $paymentId }).Count -eq 1) 'Payment history did not include the created payment.'

    $installments = @(ConvertTo-List (Invoke-PusulaApi -Method GET -Path "/installments?sale_id=$saleId"))
    $installmentRow = $installments | Where-Object { [string] $_.id -eq [string] $installmentId } | Select-Object -First 1
    Assert-True ($null -ne $installmentRow) 'Installments endpoint did not return the created installment.'
    Assert-Near ([double] $installmentRow.paid_amount) $paymentAmount 'Installment paid amount was wrong.'
    Assert-Near ([double] $installmentRow.remaining_amount) $remainingAfterPayment 'Installment remaining amount was wrong.'

    $salesWithInstallments = @(ConvertTo-List (Invoke-PusulaApi -Method GET -Path "/sales?customer_id=$customerId&with=installments"))
    Assert-True ($salesWithInstallments.Count -eq 1) "Expected one sale for customer; found $($salesWithInstallments.Count)."
    $saleRow = $salesWithInstallments[0]
    Assert-True ([string] $saleRow.id -eq [string] $saleId) 'Sales endpoint returned the wrong sale.'
    Assert-True ($saleRow.description -eq $saleUpdateDescription) 'Sale update did not persist.'
    Assert-True (@(ConvertTo-List $saleRow.installments).Count -eq 2) 'Sales endpoint did not include installments.'
    Assert-Near ([double] $saleRow.installments_paid_total) $paymentAmount 'Sales endpoint paid total was wrong.'
    Assert-Near ([double] $saleRow.installments_remaining_total) ($remainingAfterPayment + 75.00) 'Sales endpoint remaining total was wrong.'

    $report = @(ConvertTo-List (Invoke-PusulaApi -Method GET -Path "/daily-report?start=$today&end=$today"))
    $paymentRows = @($report | Where-Object {
        $_.event_type -eq 'installment_payment' -and
        [string] $_.payment_id -eq [string] $paymentId -and
        [string] $_.sale_id -eq [string] $saleId
    })
    Assert-True ($paymentRows.Count -eq 1) "Expected one matching daily report payment row; found $($paymentRows.Count)."
    Assert-Near ([double] $paymentRows[0].total) $paymentAmount 'Daily report payment total was wrong.'
    Assert-Near ([double] $paymentRows[0].amount) $paymentAmount 'Daily report payment amount was wrong.'
    Assert-Near ([double] $paymentRows[0].sale_total) $saleTotal 'Daily report payment sale_total was wrong.'
    Assert-True ([math]::Abs(([double] $paymentRows[0].total) - $saleTotal) -gt 0.001) 'Daily report total regressed to the full sale total.'

    $downPaymentRows = @($report | Where-Object {
        $_.event_type -eq 'down_payment' -and
        [string] $_.sale_id -eq [string] $saleId
    })
    Assert-True ($downPaymentRows.Count -eq 1) "Expected one daily report down-payment row; found $($downPaymentRows.Count)."
    Assert-Near ([double] $downPaymentRows[0].total) $downPayment 'Daily report down-payment amount was wrong.'

    $expectedToday = @(ConvertTo-List (Invoke-PusulaApi -Method GET -Path "/expected-payments?start=$today&end=$today"))
    $expectedRows = @($expectedToday | Where-Object { [string] $_.installment_id -eq [string] $installmentId })
    Assert-True ($expectedRows.Count -eq 1) "Expected one expected-payment row for partial installment; found $($expectedRows.Count)."
    Assert-Near ([double] $expectedRows[0].remaining_amount) $remainingAfterPayment 'Expected-payment remaining amount was wrong.'
    Assert-True ([int] $expectedRows[0].last_payment_id -eq $paymentId) 'Expected-payment row did not expose the latest payment id.'

    $offlineSnapshot = Invoke-PusulaApi -Method GET -Path '/offline-snapshot'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string] $offlineSnapshot.version)) 'Offline snapshot did not include a version.'
    Assert-True (@((ConvertTo-List $offlineSnapshot.customers) | Where-Object { [string] $_.id -eq [string] $customerId }).Count -eq 1) 'Offline snapshot did not include the customer.'
    Assert-True (@((ConvertTo-List $offlineSnapshot.sales) | Where-Object { [string] $_.id -eq [string] $saleId }).Count -eq 1) 'Offline snapshot did not include the sale.'
    Assert-True (@((ConvertTo-List $offlineSnapshot.expected_payments) | Where-Object { [string] $_.installment_id -eq [string] $installmentId }).Count -eq 1) 'Offline snapshot did not include expected payments.'

    Invoke-PusulaApi -Method DELETE -Path "/customers/$customerId" | Out-Null
    $deletedCustomerId = $customerId
    $customerId = $null

    $deletedCustomer = Invoke-PusulaApiStatus -Method GET -Path "/customers/$deletedCustomerId" -Headers $headers
    Assert-True ($deletedCustomer.StatusCode -eq 404) "Deleted customer lookup returned $($deletedCustomer.StatusCode), expected 404."

    $remainingSales = @(ConvertTo-List (Invoke-PusulaApi -Method GET -Path "/sales?customer_id=$deletedCustomerId&with=installments"))
    Assert-True ($remainingSales.Count -eq 0) "Customer delete left $($remainingSales.Count) sale rows behind."

    [pscustomobject] @{
        passed = $true
        customer_id = $deletedCustomerId
        sale_id = $saleId
        installment_id = $installmentId
        payment_id = $paymentId
        checked = @(
            'auth',
            'customer_create_read_update_search_contacts',
            'sale_create_update_idempotency',
            'installment_create_update_totals',
            'payment_create_history',
            'daily_report_payment_and_down_payment_amounts',
            'expected_payments',
            'offline_snapshot',
            'customer_delete_cascade'
        )
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
