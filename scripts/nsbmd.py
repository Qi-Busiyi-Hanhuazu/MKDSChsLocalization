import struct
from io import BufferedReader

FORMAT_DEPTH = (0, 8, 2, 4, 8, 2, 8, 16)
PALETTE_SIZE = (0x00, 0x40, 0x08, 0x20, 0x200, 0x200, 0x10, 0x00)


class TexInfo:
  def __init__(self, offset: int, size: int, width: int, height: int, format: int, depth: int):
    self.offset = offset
    self.size = size
    self.width = width
    self.height = height
    self.format = format
    self.depth = depth

    self.palette_offset = 0


class TEX0:
  def __init__(self, reader: BufferedReader):
    tex0_offset = reader.tell()

    magic, block_size = struct.unpack("<4sI", reader.read(0x08))
    assert magic == b"TEX0"

    _1, data_size, info_offset, _2, data_offset = struct.unpack("<IHHII", reader.read(0x10))
    _3, compressed_data_size, compressed_info_offset, _4, compressed_data_offset = struct.unpack(
      "<IHHII", reader.read(0x10)
    )
    compressed_data_info_offset, _5, pal_data_size, pal_info_offset = struct.unpack("<IIII", reader.read(0x10))
    (pal_data_offset,) = struct.unpack("<I", reader.read(0x04))

    reader.seek(tex0_offset + info_offset)
    _6, tex_count, section_size = struct.unpack("<BBH", reader.read(0x04))

    unk_header_size, unk_section_size, unk_constant = struct.unpack("<HHI", reader.read(0x08))
    unk_list = [struct.unpack("<2H", reader.read(0x04)) for _ in range(tex_count)]

    info_header_size, info_data_size = struct.unpack("<HH", reader.read(0x04))
    textures: list[TexInfo] = []
    for i in range(tex_count):
      tex_offset, paramaters, width2, size, __1, __2 = struct.unpack("<HHBBBB", reader.read(0x08))
      coord_transf = paramaters >> 14
      color_0 = (paramaters >> 13) & 0b1
      format = (paramaters >> 10) & 0b111
      height = 8 << ((paramaters >> 7) & 0b111)
      width = 8 << ((paramaters >> 4) & 0b111)
      flip_y = (paramaters >> 3) & 0b1
      flip_x = (paramaters >> 2) & 0b1
      repeat_y = (paramaters >> 1) & 0b1
      repeat_x = (paramaters >> 0) & 0b1

      if width == 0:
        if size & 0x3 == 2:
          width = 0x200
        else:
          width = 0x100
      if height == 0:
        if (size >> 4) & 0x3 == 2:
          height = 0x200
        else:
          height = 0x100

      textures.append(TexInfo(tex_offset << 3, size, width, height, format, FORMAT_DEPTH[format]))
      if format == 5:
        raise NotImplementedError("Format 5 not implemented")

    tex_names = [reader.read(0x10).rstrip(b"\0").decode("utf-8") for _ in range(tex_count)]

    reader.seek(tex0_offset + pal_info_offset)
    _7, pal_count, section_size = struct.unpack("<BBH", reader.read(0x04))

    unk_header_size, unk_section_size, unk_constant = struct.unpack("<HHI", reader.read(0x08))
    unk_list = [struct.unpack("<2H", reader.read(0x04)) for _ in range(tex_count)]

    info_header_size, info_data_size = struct.unpack("<HH", reader.read(0x04))
    palettes = []
    for i in range(pal_count):
      pal_offset, __1 = struct.unpack("<HH", reader.read(0x04))
      palettes.append(pal_offset & 0x1FFF)

    pal_names = [reader.read(0x10).rstrip(b"\0").decode("utf-8") for _ in range(pal_count)]
    pal_dict = dict(zip(pal_names, palettes))

    for i, tex_name in enumerate(tex_names):
      if tex_name in pal_dict:
        textures[i].palette_offset = pal_dict[tex_name]
      elif f"{tex_name}_pl" in pal_dict:
        textures[i].palette_offset = pal_dict[f"{tex_name}_pl"]

    self.textures = textures
    self.offset = tex0_offset
    self.texture_offset = data_offset
    self.texture_names = tex_names
    self.palette_offset = pal_data_offset


class NSBMD:
  def __init__(self, path):
    reader = open(path, "rb")

    magic, endianess, version, file_size, block_size, num_blocks = struct.unpack("<4sHHIHH", reader.read(0x10))

    assert magic == b"BMD0"
    assert endianess == 0xFEFF
    assert version == 0x02
    assert block_size == 0x10

    block_offsets = struct.unpack(f"<{num_blocks}I", reader.read(4 * num_blocks))

    for i, block_offset in enumerate(block_offsets):
      reader.seek(block_offset)
      magic = reader.read(4)
      if magic != b"TEX0":
        continue

      reader.seek(block_offset)
      self.tex0 = TEX0(reader)

    reader.close()
