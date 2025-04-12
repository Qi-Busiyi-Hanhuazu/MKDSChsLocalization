$env:XZ_MKDS_VERSION = "normal"

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

python scripts\generate_char_table.py
python scripts\convert_json_to_bmg.py
python scripts\convert_png_to_ncer.py
python scripts\convert_png_to_ncgr.py
python scripts\convert_png_to_nsbmd.py

New-Item -ItemType Directory -Path "temp\out\data\dwc\" -Force | Out-Null
New-Item -ItemType Directory -Path "temp\out\data\data\dwc\" -Force | Out-Null
Copy-Item -Path "files\dwc\utility.bin" -Destination "temp\out\data\dwc\utility.bin" -Recurse -Force
Copy-Item -Path "files\dwc\utility.bin" -Destination "temp\out\data\data\dwc\utility.bin" -Recurse -Force

python scripts\edit_banner.py

$versions = @("normal", "dlp")
foreach ($version in $versions) {
  $env:XZ_MKDS_VERSION = $version

  python scripts\create_font.py

  if ($version -eq "dlp") {
    Copy-Item -Path "temp\import\Main2D\LC_Font_s.NFTR" -Destination  "temp\import\Main2D\LC_Font_m.NFTR"
    Copy-Item -Path "temp\import\Main2D\LC_Font_s.NFTR" -Destination  "temp\import\Main2D\marioFont.NFTR"
  }

  python scripts\repack_carc.py

  if ($version -eq "dlp") {
    python scripts\patch_file_size.py
  }

  python scripts\create_xdelta.py

  Compress-Archive -Path "out/xdelta/", "out/banner.bin" -Destination "patch-ds.zip" -Force
  Move-Item -Path "patch-ds.zip" -Destination "out/patch-ds-$version.xzp" -Force
}
