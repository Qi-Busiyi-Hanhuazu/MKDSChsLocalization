import os

from helper import (
  DIR_TEMP_IMPORT,
  DIR_UNPACKED_FILES,
)
from nitrogfx.convert import NCGR, NCLR, Tile, nclr_to_imgpal
from PIL import Image

with open("files/ncgr_files.txt", "r", -1, "utf8") as reader:
  lines = reader.read().splitlines()

header = lines[0].split("\t")
for i, line in enumerate(lines[1:]):
  line_data = dict(zip(header, line.split("\t")))

  ncgr: NCGR = NCGR.load_from(f"unpacked/{line_data['NCGR']}")
  nclr: NCLR = NCLR.load_from(f"unpacked/{line_data['NCLR']}")
  palette_index = int(line_data.get("palette", 0))

  changed = False
  png_path = f"files/images/{line_data['NCGR']}.png"
  if not os.path.exists(png_path):
    continue

  colors = nclr_to_imgpal(nclr, palette_index)[:0x30]
  palette = Image.new("P", (8, 8))
  palette.putpalette(colors)

  image = Image.open(png_path).convert("RGBA")
  for y in range(ncgr.height):
    for x in range(ncgr.width):
      tile_image = image.crop((x * 8, y * 8, x * 8 + 8, y * 8 + 8))
      alpha_channel = tile_image.getchannel("A").tobytes()
      if any(a == 0 for a in alpha_channel):
        continue

      tile_image = tile_image.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
      tile: Tile = ncgr.tiles[y * ncgr.width + x]
      tile.pixels = tile_image.tobytes()
      changed = True

  if changed:
    new_bytes = ncgr.pack()
    ncgr_path = f"{DIR_TEMP_IMPORT}/{line_data['NCGR']}"
    os.makedirs(os.path.dirname(ncgr_path), exist_ok=True)
    with open(ncgr_path, "wb") as writer:
      with open(f"{DIR_UNPACKED_FILES}/{line_data['NCGR']}", "rb") as reader:
        writer.write(reader.read(0x30))
      writer.write(new_bytes[0x30:-0x10])
