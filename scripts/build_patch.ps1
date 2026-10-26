$env:XZ_MKDS_WIFI_TRACKS = $null

# Clean output folder
if (Test-Path -Path "out\" -PathType "Container") {
  Remove-Item -Recurse -Force "out\"
}
if (Test-Path -Path "temp\" -PathType "Container") {
  Remove-Item -Recurse -Force "temp\"
}

# Unpack/extract original files
if (-Not (Test-Path -Path "unpacked\Main2D_ja\common.bmg" -PathType "Leaf")) {
  if (Test-Path -Path "unpacked\" -PathType "Container") {
    Remove-Item -Recurse -Force "unpacked\"
  }
  python scripts\unpack_carc.py
}

python scripts\convert_png_to_ncer.py
python scripts\convert_png_to_ncgr.py
python scripts\convert_png_to_nsbmd.py

New-Item -ItemType Directory -Path "temp\out\data\dwc\" -Force | Out-Null
New-Item -ItemType Directory -Path "temp\out\data\data\dwc\" -Force | Out-Null
Copy-Item -Path "files\dwc\utility.bin" -Destination "temp\out\data\dwc\utility.bin" -Recurse -Force
Copy-Item -Path "files\dwc\utility.bin" -Destination "temp\out\data\data\dwc\utility.bin" -Recurse -Force

New-Item -ItemType Directory -Path "out\" -Force | Out-Null
New-Item -ItemType Directory -Path "out\preprocessing\" -Force | Out-Null
Copy-Item -Path "files\md5.txt" -Destination "out\md5.txt" -Recurse -Force
Copy-Item -Path "files\metadata.json" -Destination "out\metadata.json" -Recurse -Force
Copy-Item -Path "files\preprocessing\*.xdelta" -Destination "out\preprocessing" -Recurse -Force

python scripts\edit_banner.py
python scripts\generate_char_table.py
python scripts\convert_json_to_bmg.py
python scripts\create_font.py
python scripts\repack_carc.py

python scripts\patch_dlp.py
python scripts\create_xdelta.py

Compress-Archive -Path "out/xdelta/", "out/data/", "out/preprocessing/", "out/banner.bin", "out/md5.txt", "out/metadata.json" -Destination "out/patch-ds.zip" -Force
Move-Item -Path "out/patch-ds.zip" -Destination "out/patch-ds.xzp" -Force

. scripts\wifi_tracks.ps1
