$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPy = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPy)) {
  Write-Host "Missing venv python: $venvPy" -ForegroundColor Red
  exit 1
}

function Parse-BackendName([string]$name) {
  if ($name -match '^A(\d+)\.(\d+)\.(\d{2})\.py$') {
    $major = [int]$Matches[1]
    $digits = $Matches[2]
    $debug = [int]$Matches[3]
    if ($digits.Length -lt 7) { return $null }
    $dateStr = $digits.Substring($digits.Length - 7)

    $minorStr = $digits.Substring(0, $digits.Length - 7)
    if ([string]::IsNullOrWhiteSpace($minorStr)) { $minorStr = '0' }
    $minorInt = [int]$minorStr
    if ($minorStr.Length -ge 3) {
      $intPart = [int]$minorStr.Substring(0, $minorStr.Length - 2)
      $fracPart = [int]$minorStr.Substring($minorStr.Length - 2)
      $minorFloat = [double]($intPart + ($fracPart / 100.0))
    } elseif ($minorStr.Length -eq 2) {
      $minorFloat = [double]($minorInt / 100.0)
    } else {
      $minorFloat = [double]($minorInt / 10.0)
    }

    return [pscustomobject]@{
      Name       = $name
      Major      = $major
      MinorInt   = $minorInt
      MinorFloat = [double]$minorFloat
      Date       = [int]$dateStr
      Debug      = $debug
    }
  }
  return $null
}

function Parse-FrontendName([string]$name) {
  if ($name -match '^前端v0\.(\d+)\.py$') {
    $digits = $Matches[1]
    if ($digits.Length -lt 9) { return $null }
    $debug = [int]$digits.Substring($digits.Length - 2)
    $prefix = $digits.Substring(0, $digits.Length - 2)
    if ($prefix.Length -lt 7) { return $null }
    $dateStr = $prefix.Substring($prefix.Length - 7)
    $digits = $prefix

    $minorStr = $digits.Substring(0, $digits.Length - 7)
    if ([string]::IsNullOrWhiteSpace($minorStr)) { $minorStr = '0' }
    $minorInt = [int]$minorStr
    if ($minorStr.Length -ge 3) {
      $intPart = [int]$minorStr.Substring(0, $minorStr.Length - 2)
      $fracPart = [int]$minorStr.Substring($minorStr.Length - 2)
      $minorFloat = [double]($intPart + ($fracPart / 100.0))
    } elseif ($minorStr.Length -eq 2) {
      $minorFloat = [double]($minorInt / 100.0)
    } else {
      $minorFloat = [double]($minorInt / 10.0)
    }

    return [pscustomobject]@{
      Name       = $name
      MinorInt   = $minorInt
      MinorFloat = [double]$minorFloat
      Date       = [int]$dateStr
      Debug      = $debug
    }
  }
  return $null
}

# Backend is pinned to current runtime entrypoint.
$backendFixedName = 'Aphrodite demo ver.A.py'
$backendFixedPath = Join-Path $root $backendFixedName
$backendPick = $null
if (Test-Path $backendFixedPath) {
  $backendPick = [pscustomobject]@{
    Name       = $backendFixedName
    Path       = $backendFixedPath
    Major      = 0
    MinorInt   = 0
    MinorFloat = 0.0
    Date       = 0
    Debug      = 0
  }
}

$frontendCandidates = Get-ChildItem -Path $root -File -Filter '前端v0.*.py' | ForEach-Object {
  $parsed = Parse-FrontendName $_.Name
  if ($null -ne $parsed) {
    $parsed | Add-Member -NotePropertyName Path -NotePropertyValue $_.FullName
    $parsed
  }
}

if (-not $backendPick) {
  Write-Host "Backend file not found: $backendFixedName" -ForegroundColor Red
  exit 1
}
if (-not $frontendCandidates) {
  Write-Host "No frontend files found (pattern 前端v0.<digits>.py)" -ForegroundColor Red
  exit 1
}

$frontendPick = $frontendCandidates | Sort-Object Date, MinorInt, Debug | Select-Object -Last 1

$backend = $backendPick.Path
$frontend = $frontendPick.Path

$latestInfo = [pscustomobject]@{
  backend = $backendPick.Name
  frontend = $frontendPick.Name
  backend_major = $backendPick.Major
  backend_minor_int = $backendPick.MinorInt
  backend_minor = $backendPick.MinorFloat
  backend_date = $backendPick.Date
  backend_debug = $backendPick.Debug
  frontend_minor_int = $frontendPick.MinorInt
  frontend_minor = $frontendPick.MinorFloat
  frontend_date = $frontendPick.Date
  frontend_debug = $frontendPick.Debug
  updated_at = (Get-Date).ToString('s')
}

$latestJson = $latestInfo | ConvertTo-Json -Depth 2
$latestPath = Join-Path $root 'latest_versions.json'
Set-Content -Path $latestPath -Value $latestJson -Encoding UTF8

Write-Host "Starting backend: $($backendPick.Name)"
Start-Process -FilePath $venvPy -ArgumentList @('-u', "`"$backend`"") -WorkingDirectory $root

Start-Sleep -Seconds 2

Write-Host "Starting Streamlit frontend: $($frontendPick.Name)"
Start-Process -FilePath $venvPy -ArgumentList @(
  '-u','-m','streamlit','run',"`"$frontend`"",
  '--server.address','127.0.0.1',
  '--server.port','8501',
  '--browser.serverAddress','127.0.0.1',
  '--browser.serverPort','8501'
) -WorkingDirectory $root

Start-Sleep -Seconds 1
Start-Process -FilePath "cmd.exe" -ArgumentList @('/c','start','','http://127.0.0.1:8501')

Write-Host "Done. Close the console windows to stop."
