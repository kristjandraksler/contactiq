param(
    [string]$ApiBaseUrl = "https://contactiq-5w9n.onrender.com",
    [int]$BatchSize = 5,
    [int]$DelaySeconds = 2
)

$ErrorActionPreference = "Stop"

while ($true) {
    try {
        $status = Invoke-RestMethod `
            -Method Get `
            -Uri "$ApiBaseUrl/admin/worker/status"

        Write-Host (
            "Progress: {0}% | Pending: {1} | Processing: {2} | Matched: {3} | Not found: {4} | Failed: {5}" -f `
            $status.progress_percent, `
            $status.pending, `
            $status.processing, `
            $status.matched, `
            $status.not_found, `
            $status.failed
        )

        if ($status.paused) {
            Write-Host "Worker is paused."
            break
        }

        if (
            [int]$status.pending -eq 0 -and
            [int]$status.processing -eq 0
        ) {
            Write-Host "All domains are processed."
            break
        }

        $result = Invoke-RestMethod `
            -Method Post `
            -Uri "$ApiBaseUrl/admin/worker/run?limit=$BatchSize"

        Write-Host (
            "Processed batch: {0}" -f
            $result.processed_in_batch
        )

        Start-Sleep -Seconds $DelaySeconds
    }
    catch {
        Write-Host (
            "Request failed: {0}" -f $_.Exception.Message
        )
        Start-Sleep -Seconds 10
    }
}
