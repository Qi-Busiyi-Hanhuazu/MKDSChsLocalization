$env:XZ_MKDS_WIFI_TRACKS = "1"

if (Test-Path -LiteralPath "out\wifi_tracks\" -PathType "Container") {
  Remove-Item -Recurse -Force -LiteralPath "out\wifi_tracks\"
}

python scripts\patch_dlp.py
python scripts\create_xdelta.py

Compress-Archive -Path "out/wifi_tracks/xdelta/" -DestinationPath "out/patch-ds-wifi-tracks.zip" -Force
Move-Item -Path "out/patch-ds-wifi-tracks.zip" -Destination "out/patch-ds-wifi-tracks.xzp" -Force
