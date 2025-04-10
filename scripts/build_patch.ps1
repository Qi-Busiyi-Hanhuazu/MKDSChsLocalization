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

python scripts\convert_json_to_bmg.py
python scripts\create_font.py
python scripts\convert_png_to_ncer.py
python scripts\convert_png_to_ncgr.py
python scripts\convert_png_to_nsbmd.py

python scripts\repack_carc.py
python scripts\patch_file_size.py

python scripts\create_xdelta.py

python scripts\edit_banner.py

New-Item -ItemType Directory -Path "out\data\dwc\" -Force | Out-Null
New-Item -ItemType Directory -Path "out\data\data\dwc\" -Force | Out-Null
Copy-Item -Path "files\dwc\utility.bin" -Destination "out\data\dwc\utility.bin" -Recurse -Force
Copy-Item -Path "files\dwc\utility.bin" -Destination "out\data\data\dwc\utility.bin" -Recurse -Force

Compress-Archive -Path "out/data", "out/xdelta/", "out/banner.bin" -Destination "patch-ds.zip" -Force
Move-Item -Path "patch-ds.zip" -Destination "out/patch-ds.xzp" -Force
