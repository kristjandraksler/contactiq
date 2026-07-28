param(
    [string]$BaseUrl = "https://contactiq-5w9n.onrender.com",
    [int]$BatchSize = 5,
    [int]$SleepSeconds = 3,
    [int]$StallMinutes = 10,
    [int]$RequestTimeoutSeconds = 600,
    [int]$MaxRetryDelaySeconds = 60
)

$ErrorActionPreference = "Stop"

if ($BatchSize -lt 1 -or $BatchSize -gt 25) {
    throw "BatchSize mora biti med 1 in 25."
}

if ($StallMinutes -lt 5) {
    throw "StallMinutes mora biti najmanj 5."
}

$LogDirectory = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null

$LogFile = Join-Path $LogDirectory (
    "worker-{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HH-mm-ss")
)

$StartedAt = Get-Date
$LastProgressAt = Get-Date
$LastProcessed = -1
$ConsecutiveErrors = 0

function Write-WorkerLog {
    param(
        [string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::Gray
    )

    $Line = "{0} {1}" -f (
        Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    ), $Message

    Write-Host $Line -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $Line -Encoding UTF8
}

function Invoke-WorkerRequest {
    param(
        [ValidateSet("Get", "Post")]
        [string]$Method,
        [string]$Path,
        [int]$TimeoutSeconds = $RequestTimeoutSeconds
    )

    return Invoke-RestMethod `
        -Method $Method `
        -Uri "$BaseUrl$Path" `
        -TimeoutSec $TimeoutSeconds `
        -Headers @{
            Accept = "application/json"
        }
}

function Format-Duration {
    param([TimeSpan]$Duration)

    if ($Duration.TotalHours -ge 1) {
        return "{0:00}:{1:00}:{2:00}" -f `
            [math]::Floor($Duration.TotalHours), `
            $Duration.Minutes, `
            $Duration.Seconds
    }

    return "{0:00}:{1:00}" -f `
        $Duration.Minutes, `
        $Duration.Seconds
}

function Show-Status {
    param($Status)

    $Elapsed = (Get-Date) - $StartedAt
    $Processed = [int]$Status.processed
    $Total = [int]$Status.total
    $Pending = [int]$Status.pending
    $Processing = [int]$Status.processing

    $SpeedPerMinute = 0.0
    $EtaText = "—"

    if ($Elapsed.TotalMinutes -gt 0 -and $Processed -gt 0) {
        $SpeedPerMinute = $Processed / $Elapsed.TotalMinutes

        if ($SpeedPerMinute -gt 0 -and $Pending -gt 0) {
            $EtaMinutes = $Pending / $SpeedPerMinute
            $EtaText = Format-Duration (
                [TimeSpan]::FromMinutes($EtaMinutes)
            )
        }
    }

    Write-WorkerLog (
        "Progress: {0}% | Processed: {1}/{2} | Pending: {3} | " +
        "Processing: {4} | Matched: {5} | Not found: {6} | " +
        "Failed: {7} | Speed: {8:N2}/min | ETA: {9}"
    ) -f `
        $Status.progress_percent, `
        $Processed, `
        $Total, `
        $Pending, `
        $Processing, `
        $Status.matched, `
        $Status.not_found, `
        $Status.failed, `
        $SpeedPerMinute, `
        $EtaText
}

Write-WorkerLog "ContactIQ Worker v2 started." Cyan
Write-WorkerLog (
    "BaseUrl=$BaseUrl BatchSize=$BatchSize " +
    "StallMinutes=$StallMinutes Log=$LogFile"
) DarkGray

while ($true) {
    try {
        $Status = Invoke-WorkerRequest `
            -Method Get `
            -Path "/admin/worker/status" `
            -TimeoutSeconds 120

        $ConsecutiveErrors = 0
        Show-Status $Status

        if ($Status.paused -eq $true) {
            Write-WorkerLog "Worker je paused. Končujem lokalno skripto." Yellow
            break
        }

        $CurrentProcessed = [int]$Status.processed

        if ($CurrentProcessed -ne $LastProcessed) {
            $LastProcessed = $CurrentProcessed
            $LastProgressAt = Get-Date
        }

        if (
            [int]$Status.pending -eq 0 -and
            [int]$Status.processing -eq 0
        ) {
            Write-WorkerLog "Vse domene so obdelane." Green
            break
        }

        $MinutesWithoutProgress = (
            (Get-Date) - $LastProgressAt
        ).TotalMinutes

        if (
            $MinutesWithoutProgress -ge $StallMinutes -and
            [int]$Status.processing -gt 0
        ) {
            Write-WorkerLog (
                "Napredek stoji {0:N1} min. Poskušam requeue stale jobs."
                -f $MinutesWithoutProgress
            ) Yellow

            $Recovery = Invoke-WorkerRequest `
                -Method Post `
                -Path (
                    "/admin/worker/requeue-stale?stale_minutes={0}"
                    -f $StallMinutes
                ) `
                -TimeoutSeconds 120

            Write-WorkerLog (
                "Requeued stale jobs: {0}"
                -f $Recovery.requeued
            ) Yellow

            $LastProgressAt = Get-Date
            Start-Sleep -Seconds 5
            continue
        }

        $Result = Invoke-WorkerRequest `
            -Method Post `
            -Path (
                "/admin/worker/run?limit={0}"
                -f $BatchSize
            )

        $Claimed = 0
        $ProcessedInBatch = 0

        if ($null -ne $Result.claimed) {
            $Claimed = [int]$Result.claimed
        }

        if ($null -ne $Result.processed_in_batch) {
            $ProcessedInBatch = [int]$Result.processed_in_batch
        }

        if ($Claimed -gt 0) {
            $Domains = ""
            if ($null -ne $Result.domains) {
                $Domains = $Result.domains -join ", "
            }

            Write-WorkerLog (
                "Claimed: {0} | Processed: {1} | Domains: {2}"
                -f $Claimed, $ProcessedInBatch, $Domains
            ) Green
        }
        else {
            Write-WorkerLog (
                "Ni novih domen za claim. Čakam {0} sekund."
                -f $SleepSeconds
            ) DarkYellow
        }

        Start-Sleep -Seconds $SleepSeconds
    }
    catch {
        $ConsecutiveErrors += 1

        $RetryDelay = [math]::Min(
            [math]::Pow(2, [math]::Min($ConsecutiveErrors, 5)) * 5,
            $MaxRetryDelaySeconds
        )

        Write-WorkerLog (
            "Request failed: {0}"
            -f $_.Exception.Message
        ) Red

        Write-WorkerLog (
            "Retry čez {0} sekund. Consecutive errors: {1}"
            -f $RetryDelay, $ConsecutiveErrors
        ) Yellow

        Start-Sleep -Seconds $RetryDelay
    }
}

$TotalDuration = (Get-Date) - $StartedAt
Write-WorkerLog (
    "Worker končan. Trajanje: {0}"
    -f (Format-Duration $TotalDuration)
) Cyan
