import os

from helper import (
  DIR_TEMP_IMPORT,
  DIR_UNPACKED_FILES,
)
from nitrogfx.convert import NCER, NCGR, NCLR, nclr_to_imgpal
from nitrogfx.ncer import OAM, Cell
from PIL import Image

with open("files/ncer_files.txt", "r", -1, "utf8") as reader:
  lines = reader.read().splitlines()

header = lines[0].split("\t")
for i, line in enumerate(lines[1:]):
  line_data = dict(zip(header, line.split("\t")))

  ncgr: NCGR = NCGR.load_from(f"unpacked/{line_data['NCGR']}")
  nclr: NCLR = NCLR.load_from(f"unpacked/{line_data['NCLR']}")
  ncer: NCER = NCER.load_from(f"unpacked/{line_data['NCER']}")

  cells: list[Cell] = ncer.cells
  changed = False
  for j, cell in enumerate(cells):
    png_path = f"files/images/{line_data['NCER']}_{j}.png"
    if not os.path.exists(png_path):
      continue

    cell_image = Image.open(png_path)
    if cell_image.size != (512, 256):
      continue
    if cell_image.mode in {"RGBA", "P"}:
      cell_image = cell_image.convert("RGBA")

    oams: list[OAM] = cell.oam
    for k, oam in enumerate(oams[::-1]):
      oam_width, oam_height = oam.get_size()
      x_offset = (oam.x + 0x100) % 0x200
      y_offset = (oam.y + 0x80) % 0x100

      oam_image = cell_image.crop((x_offset, y_offset, x_offset + oam_width, y_offset + oam_height))
      alphas = oam_image.getchannel("A").tobytes()
      if any(a == 0 for a in alphas):
        continue
      oam_image = oam_image.convert("RGB")

      if oam.rot == 0:
        if (oam.rotsca >> 3) & 1:
          oam_image = oam_image.transpose(Image.FLIP_LEFT_RIGHT)
        if (oam.rotsca >> 4) & 1:
          oam_image = oam_image.transpose(Image.FLIP_TOP_BOTTOM)

      tile_index = oam.char
      for y in range(0, oam_height, 8):
        for x in range(0, oam_width, 8):
          tile_image = oam_image.crop((x, y, x + 8, y + 8))

          colors = nclr_to_imgpal(nclr, oam.pal)[:0x30]
          palette = Image.new("P", (8, 8))
          palette.putpalette(colors)
          tile_image = tile_image.quantize(palette=palette, dither=Image.NONE)
          ncgr.tiles[tile_index].pixels = tile_image.tobytes()

          tile_index += 1

    changed = True

  if changed:
    new_bytes = ncgr.pack()
    ncgr_path = f"{DIR_TEMP_IMPORT}/{line_data['NCGR']}"
    os.makedirs(os.path.dirname(ncgr_path), exist_ok=True)
    with open(ncgr_path, "wb") as writer:
      with open(f"{DIR_UNPACKED_FILES}/{line_data['NCGR']}", "rb") as reader:
        writer.write(reader.read(0x30))
      writer.write(new_bytes[0x30:-0x10])
