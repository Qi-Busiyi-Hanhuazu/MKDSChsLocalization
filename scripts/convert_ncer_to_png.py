import os

from nitrogfx.convert import NCER, NCGR, NCLR, OAM, Cell, Tile, nclr_to_imgpal
from PIL import Image
from convert_nclr_to_act import nclr_to_act

with open("files/ncer_files.txt", "r", -1, "utf8") as reader:
  lines = reader.read().splitlines()

header = lines[0].split("\t")
for i, line in enumerate(lines[1:]):
  line_data = dict(zip(header, line.split("\t")))

  ncgr: NCGR = NCGR.load_from(f"unpacked/{line_data['NCGR']}")
  nclr: NCLR = NCLR.load_from(f"unpacked/{line_data['NCLR']}")
  ncer: NCER = NCER.load_from(f"unpacked/{line_data['NCER']}")

  cells: list[Cell] = ncer.cells

  for j, cell in enumerate(cells):
    oams: list[OAM] = cell.oam
    cell_image = Image.new("RGBA", (512, 256))
    for k, oam in enumerate(oams[::-1]):
      oam_width, oam_height = oam.get_size()
      x_offset = (oam.x + 0x100) % 0x200
      y_offset = (oam.y + 0x80) % 0x100

      oam_image = Image.new("RGBA", (oam_width, oam_height))
      tile_index = oam.char
      for y in range(0, oam_height, 8):
        for x in range(0, oam_width, 8):
          tile: Tile = ncgr.tiles[tile_index]
          tile_image = Image.frombytes("P", (8, 8), tile.get_data())
          tile_image.putpalette(nclr_to_imgpal(nclr, oam.pal))
          oam_image.paste(tile_image, (x, y))
          tile_index += 1

      if oam.rot == 0:
        if (oam.rotsca >> 3) & 1:
          oam_image = oam_image.transpose(Image.FLIP_LEFT_RIGHT)
        if (oam.rotsca >> 4) & 1:
          oam_image = oam_image.transpose(Image.FLIP_TOP_BOTTOM)
      cell_image.paste(oam_image, (x_offset, y_offset))

    png_path = f"temp/images/{line_data['NCER']}_{j}.png"
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    cell_image.save(png_path)
    act_path = f"temp/images/{line_data['NCER']}_{j}.act"
    nclr_to_act(nclr, act_path, index=oam.pal, bpp=ncgr.bpp)
