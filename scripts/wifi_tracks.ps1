$ErrorActionPreference = "Stop"
if ((Get-Location).Path -ne (Split-Path -Parent $PSScriptRoot)) {
  throw "Run scripts\wifi_tracks.ps1 from the repository root."
}
if (Test-Path -LiteralPath "out\wifi_tracks\" -PathType "Container") {
  Remove-Item -Recurse -Force -LiteralPath "out\wifi_tracks\"
}

$env:XZ_MKDS_WIFI_TRACKS = "1"
try {
  python scripts\patch_dlp.py
  if ($LASTEXITCODE -ne 0) { throw "Failed to create the Wi-Fi track add-on." }
  python scripts\create_xdelta.py
  if ($LASTEXITCODE -ne 0) { throw "Failed to create the Wi-Fi track patch." }
} finally {
  Remove-Item Env:XZ_MKDS_WIFI_TRACKS
}

Compress-Archive -Path "out/wifi_tracks/xdelta/" -DestinationPath "out/patch-ds-wifi-tracks.zip" -Force
Move-Item -Path "out/patch-ds-wifi-tracks.zip" -Destination "out/patch-ds-wifi-tracks.xzp" -Force
