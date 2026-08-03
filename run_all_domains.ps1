param(
    [string]$BaseUrl = "https://contactiq-5w9n.onrender.com",
    [int]$BatchSize = 5,
    [int]$SleepSeconds = 3,
    [int]$StallMinutes = 10,
    [int]$RequestTimeoutSeconds = 600,
    [switch]$IncludePublicEmails
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

$LogFile = Join-Path $LogDirectory ("worker-" + (Get-Date -Format "yyyy-MM-dd_HH-mm-ss") + ".log")

$StartedAt = Get-Date
$LastProgressAt = Get-Date
$LastProcessed = -1
$ConsecutiveErrors = 0
$RecoveryEndpointAvailable = $true

function Write-LogLine {
    param(
        [string]$Message,
        [string]$Color = "Gray"
    )

    $Line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $Message
    Write-Host $Line -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $Line -Encoding UTF8
}

function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [int]$TimeoutSeconds
    )

    return Invoke-RestMethod -Method $Method -Uri ($BaseUrl + $Path) -TimeoutSec $TimeoutSeconds -Headers @{ Accept = "application/json" }
}

function Format-TimeSpan {
    param([TimeSpan]$Value)

    if ($Value.TotalHours -ge 1) {
        $Hours = [math]::Floor($Value.TotalHours)
        return ("{0:00}:{1:00}:{2:00}" -f $Hours, $Value.Minutes, $Value.Seconds)
    }

    return ("{0:00}:{1:00}" -f $Value.Minutes, $Value.Seconds)
}

Write-LogLine -Message "ContactIQ Worker v2 started." -Color "Cyan"
$Mode = if ($IncludePublicEmails) { "PUBLIC_EMAIL_RESEARCH" } else { "STANDARD" }

Write-LogLine -Message ("BaseUrl=" + $BaseUrl + " BatchSize=" + $BatchSize + " StallMinutes=" + $StallMinutes + " Mode=" + $Mode + " Log=" + $LogFile) -Color "DarkGray"

if ($IncludePublicEmails) {
    Write-LogLine -Message "Research mode je vklopljen. Public providerji se pregledajo, vendar se sprejmejo samo person-specific zadetki." -Color "Yellow"
}

while ($true) {
    try {
        $Status = Invoke-Api -Method "Get" -Path "/admin/worker/status" -TimeoutSeconds 120

        $ConsecutiveErrors = 0

        $Elapsed = (Get-Date) - $StartedAt
        $Processed = [int]$Status.processed
        $Total = [int]$Status.total
        $Pending = [int]$Status.pending
        $Processing = [int]$Status.processing
        $Matched = [int]$Status.matched
        $NotFound = [int]$Status.not_found
        $Failed = [int]$Status.failed

        $SpeedPerMinute = 0.0
        $EtaText = "-"

        if ($Elapsed.TotalMinutes -gt 0 -and $Processed -gt 0) {
            $SpeedPerMinute = $Processed / $Elapsed.TotalMinutes

            if ($SpeedPerMinute -gt 0 -and $Pending -gt 0) {
                $EtaMinutes = $Pending / $SpeedPerMinute
                $EtaText = Format-TimeSpan -Value ([TimeSpan]::FromMinutes($EtaMinutes))
            }
        }

        $StatusLine = "Progress: " + $Status.progress_percent + "% | Processed: " + $Processed + "/" + $Total + " | Pending: " + $Pending + " | Processing: " + $Processing + " | Matched: " + $Matched + " | Not found: " + $NotFound + " | Failed: " + $Failed + " | Speed: " + ([math]::Round($SpeedPerMinute, 2)) + "/min | ETA: " + $EtaText
        Write-LogLine -Message $StatusLine -Color "Cyan"

        if ($Status.paused -eq $true) {
            Write-LogLine -Message "Worker je paused. Koncujem lokalno skripto." -Color "Yellow"
            break
        }

        if ($Processed -ne $LastProcessed) {
            $LastProcessed = $Processed
            $LastProgressAt = Get-Date
        }

        if ($Pending -eq 0 -and $Processing -eq 0) {
            Write-LogLine -Message "Vse domene so obdelane." -Color "Green"
            break
        }

        $MinutesWithoutProgress = ((Get-Date) - $LastProgressAt).TotalMinutes

        if (
            $MinutesWithoutProgress -ge $StallMinutes `
            -and $Processing -gt 0 `
            -and $RecoveryEndpointAvailable
        ) {
            $RoundedMinutes = [math]::Round($MinutesWithoutProgress, 1)
            Write-LogLine -Message ("Napredek stoji " + $RoundedMinutes + " min. Poskusam requeue stale jobs.") -Color "Yellow"

            try {
                $RecoveryPath = "/admin/worker/requeue-stale?stale_minutes=" + $StallMinutes
                $Recovery = Invoke-Api -Method "Post" -Path $RecoveryPath -TimeoutSeconds 120

                Write-LogLine -Message ("Requeued stale jobs: " + $Recovery.requeued) -Color "Yellow"

                $LastProgressAt = Get-Date
                Start-Sleep -Seconds 5
                continue
            }
            catch {
                $StatusCode = $null

                if (
                    $_.Exception.Response `
                    -and $_.Exception.Response.StatusCode
                ) {
                    $StatusCode = [int]$_.Exception.Response.StatusCode
                }

                if ($StatusCode -eq 404) {
                    $RecoveryEndpointAvailable = $false
                    $LastProgressAt = Get-Date

                    Write-LogLine -Message "Recovery endpoint /requeue-stale ni na voljo. Avtomatski requeue je izklopljen za ta zagon." -Color "Yellow"
                }
                else {
                    throw
                }
            }
        }

        $RunPath = "/admin/worker/run?limit=" + $BatchSize

        if ($IncludePublicEmails) {
            $RunPath = $RunPath + "&include_public_emails=true"
        }
        $Result = Invoke-Api -Method "Post" -Path $RunPath -TimeoutSeconds $RequestTimeoutSeconds

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

            Write-LogLine -Message ("Claimed: " + $Claimed + " | Processed: " + $ProcessedInBatch + " | Domains: " + $Domains) -Color "Green"
        }
        else {
            Write-LogLine -Message ("Ni novih domen za claim. Cakam " + $SleepSeconds + " sekund.") -Color "DarkYellow"
        }

        Start-Sleep -Seconds $SleepSeconds
    }
    catch {
        $ConsecutiveErrors = $ConsecutiveErrors + 1

        $RetryDelay = [math]::Min(([math]::Pow(2, [math]::Min($ConsecutiveErrors, 5)) * 5), 60)

        Write-LogLine -Message ("Request failed: " + $_.Exception.Message) -Color "Red"
        Write-LogLine -Message ("Retry cez " + $RetryDelay + " sekund. Consecutive errors: " + $ConsecutiveErrors) -Color "Yellow"

        Start-Sleep -Seconds $RetryDelay
    }
}

$TotalDuration = (Get-Date) - $StartedAt
Write-LogLine -Message ("Worker koncan. Trajanje: " + (Format-TimeSpan -Value $TotalDuration)) -Color "Cyan"
