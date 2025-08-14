# Start a dedicated Chrome instance with remote debugging on 9224 and isolated profile
param(
  [int]$Port = 9224,
  [string]$Url = "http://localhost:8000/"
)

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
  $chrome = "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe"
}

$userData = Join-Path $env:LOCALAPPDATA "ChromeMCP"
Write-Host "Starting browser: $chrome on port $Port with profile $userData"
& "$chrome" --remote-debugging-port=$Port --remote-debugging-address=0.0.0.0 --user-data-dir="$userData" "$Url"


