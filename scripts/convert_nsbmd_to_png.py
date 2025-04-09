import os
import struct

from helper import DIR_UNPACKED_FILES
from nitrogfx.util import rgb555_to_color
from nsbmd import NSBMD
from PIL import Image

for root, dirs, files in os.walk(DIR_UNPACKED_FILES):
  for file_name in files:
    if not file_name.endswith(".nsbmd"):
      continue

    if "_ja" not in root:
      continue

    path = f"{root}/{file_name}"
    relative_path = os.path.relpath(path, DIR_UNPACKED_FILES)

    file = NSBMD(path)
    tex0 = file.tex0

    with open(path, "rb") as reader:
      for i, tex in enumerate(tex0.textures):
        assert tex.format == 3
        name = tex0.texture_names[i]

        reader.seek(tex0.offset + tex0.palette_offset + tex.palette_offset * 8)
        colors = []
        for _ in struct.unpack("<16H", reader.read(0x20)):
          color = rgb555_to_color(_)
          colors.append(color[0])
          colors.append(color[1])
          colors.append(color[2])

        image_bytes = bytearray()
        reader.seek(tex0.offset + tex0.texture_offset + tex.offset)
        for _ in range(tex.width * tex.height // 2):
          byte = reader.read(1)[0]
          image_bytes.append(byte & 0xF)
          image_bytes.append(byte >> 4)

        image = Image.frombytes("P", (tex.width, tex.height), bytes(image_bytes))
        image.putpalette(colors)
        image = image.convert("RGB")

        image_path = f"temp/images/{relative_path.removesuffix('.nsbmd')}_{name}.png"
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        image.save(image_path)
