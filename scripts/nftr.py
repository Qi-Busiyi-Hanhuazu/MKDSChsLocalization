import io
import struct
from io import BufferedReader
from math import ceil

from PIL import Image


class FINF:
  def __init__(self, reader: BufferedReader):
    magic, block_size = struct.unpack("<4sI", reader.read(0x08))
    self.block_size: int = block_size

    assert magic == b"FNIF"

    unk1, height, null_char_index, default_start, default_width, default_length, encoding = struct.unpack(
      "<2BH4B", reader.read(0x08)
    )
    self.unk1: int = unk1
    self.height: int = height
    self.null_char_index: int = null_char_index
    self.default_start: int = default_start
    self.default_width: int = default_width
    self.default_length: int = default_length
    self.encoding: int = encoding

    cglp_offset, cwdh_offset, cmap_offset = struct.unpack("<3I", reader.read(0x0C))
    self.cglp_offset: int = cglp_offset
    self.cwdh_offset: int = cwdh_offset
    self.cmap_offset: int = cmap_offset

    if block_size == 0x20:
      font_height, font_width, bearing_y, bearing_x = struct.unpack("<4B", reader.read(0x04))
      self.font_height: int = font_height
      self.font_width: int = font_width
      self.bearing_y: int = bearing_y
      self.bearing_x: int = bearing_x

  def get_bytes(self) -> bytes:
    if hasattr(self, "font_height"):
      body = struct.pack("<4B", self.font_height, self.font_width, self.bearing_y, self.bearing_x)
    else:
      body = b""
    head = struct.pack(
      "<4sI2BH4B3I",
      b"FNIF",
      0x1C + len(body),
      self.unk1,
      self.height,
      self.null_char_index,
      self.default_start,
      self.default_width,
      self.default_length,
      self.encoding,
      self.cglp_offset,
      self.cwdh_offset,
      self.cmap_offset,
    )
    return bytes(head + body)


class CGLPTile:
  def __init__(self, width: int, height: int, depth: int, raw_bytes: bytes):
    self.width = width
    self.height = height
    self.depth = depth
    self.raw_bytes = raw_bytes

  def get_image(self) -> Image.Image:
    bitmap = Image.new("L", (self.width, self.height))
    bits = []
    if self.depth == 1:
      multiplier = 0xFF
      for byte in self.raw_bytes:
        for i in range(7, -1, -1):
          bits.append((byte >> i) & 0b1)
    elif self.depth == 2:
      multiplier = 0x55
      for byte in self.raw_bytes:
        for i in range(3, -1, -1):
          bits.append((byte >> 2 * i) & 0b11)
    elif self.depth == 3:
      multiplier = 0x24
      for pos in range(0, len(self.raw_bytes), 3):
        triple = self.raw_bytes[pos : pos + 3]
        (int_24,) = struct.unpack(">I", b"\0" + triple)
        for i in range(7, -1, -1):
          bits.append((int_24 >> 3 * i) & 0b111)
    elif self.depth == 4:
      multiplier = 0x11
      for byte in self.raw_bytes:
        for i in range(1, -1, -1):
          bits.append((byte >> 4 * i) & 0b1111)

    pos = 0
    for y in range(self.height):
      for x in range(self.width):
        bit = bits[pos]
        pos += 1
        bitmap.putpixel((x, y), 0xFF - bit * multiplier)

    return bitmap

  def get_bytes(self, bitmap: Image.Image) -> bytes:
    if self.depth == 1:
      multiplier = 0xFF
    elif self.depth == 2:
      multiplier = 0x55
    elif self.depth == 3:
      multiplier = 0x24
    elif self.depth == 4:
      multiplier = 0x11

    bits = []
    for y in range(self.height):
      for x in range(self.width):
        pixel = bitmap.getpixel((x, y))
        bits.append(round((0xFF - pixel) / multiplier))

    raw_bytes = bytearray()
    if self.depth == 1:
      pos = 0
      while pos < len(bits):
        byte = 0
        for i in range(7, -1, -1):
          byte |= bits[pos] << i
          pos += 1
          if pos >= len(bits):
            break
        raw_bytes.append(byte)
    elif self.depth == 2:
      pos = 0
      while pos < len(bits):
        byte = 0
        for i in range(3, -1, -1):
          byte |= bits[pos] << 2 * i
          pos += 1
          if pos >= len(bits):
            break
        raw_bytes.append(byte)
    elif self.depth == 3:
      pos = 0
      while pos < len(bits):
        triple = 0
        for i in range(7, -1, -1):
          triple |= bits[pos] << 3 * i
          pos += 1
          if pos >= len(bits):
            break
        raw_bytes += struct.pack(">I", triple)[-3:]
    elif self.depth == 4:
      pos = 0
      while pos < len(bits):
        byte = 0
        for i in range(1, -1, -1):
          byte |= bits[pos] << 4 * i
          pos += 1
          if pos >= len(bits):
            break
        raw_bytes.append(byte)

    return bytes(raw_bytes)


class CGLP:
  def __init__(self, reader: BufferedReader):
    magic, block_size = struct.unpack("<4sI", reader.read(0x08))

    assert magic == b"PLGC"

    tile_width, tile_height, tile_length, unk, depth, rotate_mode = struct.unpack("<2B2H2B", reader.read(0x08))
    self.tile_width: int = tile_width
    self.tile_height: int = tile_height
    assert tile_length == ceil(tile_width * tile_height * depth / 8)
    self.unk: int = unk
    self.depth: int = depth
    self.rotate_mode: int = rotate_mode
    self.tiles: list[CGLPTile] = []
    for i in range(0, (block_size - 0x10) // tile_length):
      self.tiles.append(CGLPTile(tile_width, tile_height, depth, reader.read(tile_length)))

  def get_bytes(self) -> bytes:
    body = bytearray()
    for tile in self.tiles:
      body += tile.raw_bytes
    body += b"\0" * (-len(body) % 4)

    tile_length = ceil(self.tile_width * self.tile_height * self.depth / 8)
    head = struct.pack(
      "<4sI2B2H2B",
      b"PLGC",
      0x10 + len(body),
      self.tile_width,
      self.tile_height,
      tile_length,
      self.unk,
      self.depth,
      self.rotate_mode,
    )
    return bytes(head + body)


class CWDHInfo:
  def __init__(self, start: int, width: int, length: int):
    self.start: int = start
    self.width: int = width
    self.length: int = length

  def get_bytes(self) -> bytes:
    return struct.pack("<b2B", self.start, self.width, self.length)


class CWDH:
  def __init__(self, reader: BufferedReader):
    magic, block_size = struct.unpack("<4sI", reader.read(0x08))

    assert magic == b"HDWC"

    first_code, last_code, unk1 = struct.unpack("<2HI", reader.read(0x08))
    self.first_code: int = first_code
    self.last_code: int = last_code
    self.unk1: int = unk1

    self.info: list[CWDHInfo] = []
    for i in range(0, (block_size - 0x10) // 3):
      start, width, length = struct.unpack("<b2B", reader.read(0x03))
      self.info.append(CWDHInfo(start, width, length))

  def get_bytes(self):
    body = bytearray()
    for info in self.info:
      body += info.get_bytes()
    body += b"\0" * (-len(body) % 4)

    head = struct.pack("<4sI2HI", b"HDWC", 0x10 + len(body), 0, len(self.info) - 1, self.unk1)
    return bytes(head + body)


class CMAP:
  def __init__(self, reader: BufferedReader):
    magic, block_size = struct.unpack("<4sI", reader.read(0x08))

    assert magic == b"PAMC"

    first_char_code, last_char_code, type_section, next_offset = struct.unpack("<2H2I", reader.read(0x0C))
    self.first_char_code: int = first_char_code
    self.last_char_code: int = last_char_code
    self.type_section: int = type_section
    self.next_offset: int = next_offset

    self.index_map: dict[int, int] = {}
    if self.type_section == 0:
      (first_char_index,) = struct.unpack("<H", reader.read(0x02))
      for i in range(last_char_code - first_char_code + 1):
        char_index = first_char_index + i
        self.index_map[first_char_code + i] = char_index
    elif self.type_section == 1:
      length = last_char_code - first_char_code + 1
      for i in range(length):
        (char_index,) = struct.unpack("<H", reader.read(0x02))
        if char_index == 0xFFFF:
          continue
        self.index_map[first_char_code + i] = char_index
    elif self.type_section == 2:
      (num_chars,) = struct.unpack("<H", reader.read(0x02))
      for i in range(num_chars):
        char_code, char_index = struct.unpack("<2H", reader.read(0x04))
        self.index_map[char_code] = char_index

  @property
  def char_map(self) -> dict[int, int]:
    return {v: k for k, v in self.index_map.items()}

  @staticmethod
  def get_blank():
    with io.BytesIO() as buffer:
      buffer.write(b"PAMC" + b"\0" * 0x12)
      buffer.seek(0)
      cmap = CMAP(buffer)
    return cmap

  def get_bytes(self, index_map: dict[int, int] = None) -> bytes:
    if index_map is None:
      index_map = self.index_map
    sorted_keys = sorted(index_map.keys(), key=lambda x: index_map[x])
    body = bytearray()
    if self.type_section == 0:
      for char_code, char_index in index_map.items():
        body += struct.pack("<H", char_index)
        break
    elif self.type_section == 1:
      length = self.last_char_code - self.first_char_code + 1
      for i in range(length):
        char_code = self.first_char_code + i
        char_index = index_map.get(char_code, 0xFFFF)
        body += struct.pack("<H", char_index)
    elif self.type_section == 2:
      body += struct.pack("<H", len(index_map))
      for key in sorted_keys:
        body += struct.pack("<2H", key, index_map[key])

    body += b"\0" * (-len(body) % 4)

    head = struct.pack(
      "<4sI2H2I",
      b"PAMC",
      0x14 + len(body),
      self.first_char_code,
      self.last_char_code,
      self.type_section,
      0,
    )
    return bytes(head + body)


class NFTR:
  def __init__(self, FONT_PATH: str):
    reader = open(FONT_PATH, "rb")

    magic, endianess, unk1, file_size, block_size, num_blocks = struct.unpack("<4sHHIHH", reader.read(0x10))

    assert magic == b"RTFN"
    assert endianess == 0xFEFF
    assert block_size == 0x10

    self.unk1: int = unk1
    self.num_blocks: int = num_blocks

    self.finf: FINF = FINF(reader)

    reader.seek(self.finf.cglp_offset - 0x08)
    self.cglp: CGLP = CGLP(reader)

    reader.seek(self.finf.cwdh_offset - 0x08)
    self.cwdh: CWDH = CWDH(reader)

    self.char_map: dict[int, int] = {}
    self.cmaps: list[CMAP] = []
    next_offset = self.finf.cmap_offset - 0x08
    while next_offset >= reader.tell():
      reader.seek(next_offset)
      cmap = CMAP(reader)
      self.cmaps.append(cmap)
      self.char_map.update(cmap.char_map)
      next_offset = cmap.next_offset - 0x08

  def get_bytes(self) -> bytes:
    cmaps = [cmap.get_bytes() for cmap in self.cmaps]
    cwdh = self.cwdh.get_bytes()
    cglp = self.cglp.get_bytes()

    self.finf.cglp_offset = 0x18 + self.finf.block_size
    self.finf.cwdh_offset = self.finf.cglp_offset + len(cglp)
    self.finf.cmap_offset = self.finf.cwdh_offset + len(cwdh)
    next_offset = self.finf.cmap_offset
    for i, cmap in enumerate(cmaps[:-1]):
      next_offset += len(cmap)
      cmaps[i] = cmap[:0x10] + struct.pack("<I", next_offset) + cmap[0x14:]

    finf = self.finf.get_bytes()

    body = finf + cglp + cwdh + b"".join(cmaps)

    head = struct.pack("<4sHHIHH", b"RTFN", 0xFEFF, self.unk1, 0x10 + len(body), 0x10, 0x03 + len(cmaps))
    return bytes(head + body)
