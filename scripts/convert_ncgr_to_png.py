import os

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

  image = Image.new("RGB", (ncgr.width * 8, ncgr.height * 8))
  for y in range(ncgr.height):
    for x in range(ncgr.width):
      tile: Tile = ncgr.tiles[y * ncgr.width + x]
      tile_image = Image.frombytes("P", (8, 8), tile.get_data())
      tile_image.putpalette(nclr_to_imgpal(nclr, palette_index))

      image.paste(tile_image, (x * 8, y * 8))

  png_path = f"temp/images/{line_data['NCGR']}.png"
  os.makedirs(os.path.dirname(png_path), exist_ok=True)
  image.save(png_path)
