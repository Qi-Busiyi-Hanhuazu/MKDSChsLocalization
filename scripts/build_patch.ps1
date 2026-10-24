$ErrorActionPreference = "Stop"
if ((Get-Location).Path -ne (Split-Path -Parent $PSScriptRoot)) {
  throw "Run scripts\build_patch.ps1 from the repository root."
}
$env:XZ_MKDS_WIFI_TRACKS = $null

# Clean output folders, keeping ROMs and save files in out
foreach ($path in @("out\xdelta\", "out\preprocessing\", "temp\")) {
  if (Test-Path -LiteralPath $path -PathType "Container") {
    Remove-Item -Recurse -Force -LiteralPath $path
  }
}

make -C arm9_patch clean
if ($LASTEXITCODE -ne 0) { throw "Failed to clean the compiled patches." }

# Unpack/extract original files
if (-Not (Test-Path -Path "unpacked\Main2D_ja\common.bmg" -PathType "Leaf")) {
  if (Test-Path -Path "unpacked\" -PathType "Container") {
    Remove-Item -Recurse -Force "unpacked\"
  }
  python scripts\unpack_carc.py
  if ($LASTEXITCODE -ne 0) { throw "Failed to unpack the original files." }
}

python scripts\convert_png_to_ncer.py
if ($LASTEXITCODE -ne 0) { throw "Failed to convert NCER images." }
python scripts\convert_png_to_ncgr.py
if ($LASTEXITCODE -ne 0) { throw "Failed to convert NCGR images." }
python scripts\convert_png_to_nsbmd.py
if ($LASTEXITCODE -ne 0) { throw "Failed to convert NSBMD images." }

New-Item -ItemType Directory -Path "temp\out\data\dwc\" -Force | Out-Null
New-Item -ItemType Directory -Path "temp\out\data\data\dwc\" -Force | Out-Null
Copy-Item -Path "files\dwc\utility.bin" -Destination "temp\out\data\dwc\utility.bin" -Recurse -Force
Copy-Item -Path "files\dwc\utility.bin" -Destination "temp\out\data\data\dwc\utility.bin" -Recurse -Force

New-Item -ItemType Directory -Path "out\" -Force | Out-Null
New-Item -ItemType Directory -Path "out\preprocessing\" -Force | Out-Null
Copy-Item -Path "files\md5.txt" -Destination "out\md5.txt" -Recurse -Force
Copy-Item -Path "files\preprocessing\*.xdelta" -Destination "out\preprocessing" -Recurse -Force

python scripts\edit_banner.py
if ($LASTEXITCODE -ne 0) { throw "Failed to create the banner." }
python scripts\generate_char_table.py
if ($LASTEXITCODE -ne 0) { throw "Failed to generate the character table." }
python scripts\convert_json_to_bmg.py
if ($LASTEXITCODE -ne 0) { throw "Failed to convert the messages." }
python scripts\create_font.py
if ($LASTEXITCODE -ne 0) { throw "Failed to create the fonts." }
python scripts\repack_carc.py
if ($LASTEXITCODE -ne 0) { throw "Failed to repack the archives." }

python scripts\patch_dlp.py
if ($LASTEXITCODE -ne 0) { throw "Failed to create Download Play files." }
python scripts\create_xdelta.py
if ($LASTEXITCODE -ne 0) { throw "Failed to create the file patches." }

Compress-Archive -Path "out/xdelta/", "out/preprocessing/", "out/banner.bin", "out/md5.txt" -Destination "out/patch-ds.zip" -Force
Move-Item -Path "out/patch-ds.zip" -Destination "out/patch-ds.xzp" -Force

. scripts\wifi_tracks.ps1
