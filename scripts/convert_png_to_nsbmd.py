import os
import shutil
import struct

from helper import DIR_TEMP_IMPORT, DIR_UNPACKED_FILES
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

    writer = None

    with open(path, "rb") as reader:
      for i, tex in enumerate(tex0.textures):
        assert tex.format == 3
        name = tex0.texture_names[i]
        image_path = f"files/images/{relative_path.removesuffix('.nsbmd')}_{name}.png"
        if not os.path.exists(image_path):
          continue
        if not writer:
          output_path = f"{DIR_TEMP_IMPORT}/{relative_path}"
          os.makedirs(os.path.dirname(output_path), exist_ok=True)
          shutil.copy(path, output_path)
          writer = open(output_path, "r+b")

        reader.seek(tex0.offset + tex0.palette_offset + tex.palette_offset * 8)
        colors = []
        for _ in struct.unpack("<16H", reader.read(0x20)):
          color = rgb555_to_color(_)
          colors.append(color[0])
          colors.append(color[1])
          colors.append(color[2])

        palette = Image.new("P", (8, 8))
        palette.putpalette(colors)

        image = Image.open(image_path).convert("RGB")
        image = image.quantize(palette=palette, dither=Image.Dither.NONE)

        image_bytes = image.tobytes()
        raw_bytes = bytearray()

        for i in range(0, len(image_bytes), 2):
          raw_bytes.append((image_bytes[i + 1] << 4) | image_bytes[i])

        writer.seek(tex0.offset + tex0.texture_offset + tex.offset)
        writer.write(raw_bytes)

    if writer:
      writer.close()
