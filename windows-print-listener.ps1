param(
    [string]$ServerUrl = "http://127.0.0.1:8000",
    [string]$PrinterName = "HP Printer",
    [int]$PollSeconds = 2
)

Write-Host "Listening for warehouse orders from $ServerUrl"
Write-Host "Printing to $PrinterName"

while ($true) {
    try {
        $nextOrder = Invoke-RestMethod -Uri "$ServerUrl/api/print/next" -Method Get
        if ($null -ne $nextOrder.order) {
            $ticketPath = Join-Path $env:TEMP "$($nextOrder.order.id)-ticket.txt"
            [System.IO.File]::WriteAllText($ticketPath, $nextOrder.order.ticket)
            Get-Content $ticketPath | Out-Printer -Name $PrinterName
            Invoke-RestMethod -Uri "$ServerUrl/api/print/ack" -Method Post -ContentType "application/json" -Body (@{ order_id = $nextOrder.order.id } | ConvertTo-Json)
            Write-Host "Printed order $($nextOrder.order.id) at $(Get-Date -Format s)"
        }
    }
    catch {
        Write-Warning $_.Exception.Message
    }

    Start-Sleep -Seconds $PollSeconds
}
