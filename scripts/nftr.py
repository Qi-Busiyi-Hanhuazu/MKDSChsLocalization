from __future__ import annotations

import struct
from io import BufferedReader
from math import ceil
from typing import Literal, TypeAlias

from PIL import Image

Endianess: TypeAlias = Literal["<", ">"]


class FINF:
  def __init__(self, data: bytes, offset: int = 0, magic_endinaness: Endianess = "<", endianess: Endianess = "<"):
    magic, block_size = struct.unpack_from(f"{endianess}4sI", data, offset)
    self.block_size: int = block_size

    if magic_endinaness == ">":
      assert magic == b"FINF"
    else:
      assert magic == b"FNIF"

    font_type, line_height, default_glyph_index, default_start, default_width, default_length, encoding = (
      struct.unpack_from(f"{endianess}2BH4B", data, offset + 0x08)
    )
    self.font_type: int = font_type
    self.line_height: int = line_height
    self.default_glyph_index: int = default_glyph_index
    self.default_start: int = default_start
    self.default_width: int = default_width
    self.default_length: int = default_length
    self.encoding: int = encoding

    cglp_offset, cwdh_offset, cmap_offset = struct.unpack_from(f"{endianess}3I", data, offset + 0x10)
    self.cglp_offset: int = cglp_offset
    self.cwdh_offset: int = cwdh_offset
    self.cmap_offset: int = cmap_offset

    if block_size == 0x20:
      font_height, font_width, bearing_y, bearing_x = struct.unpack_from(f"{endianess}4B", data, offset + 0x1C)
      self.font_height: int = font_height
      self.font_width: int = font_width
      self.bearing_y: int = bearing_y
      self.bearing_x: int = bearing_x

  def get_bytes(self, magic_endinaness: Endianess = "<", endianess: Endianess = "<") -> bytes:
    if hasattr(self, "font_height"):
      body = struct.pack(f"{endianess}4B", self.font_height, self.font_width, self.bearing_y, self.bearing_x)
    else:
      body = b""
    head = struct.pack(
      f"{endianess}4sI2BH4B3I",
      b"FINF" if magic_endinaness == ">" else b"FNIF",
      0x1C + len(body),
      self.font_type,
      self.line_height,
      self.default_glyph_index,
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
  def __init__(self, width: int, height: int, bpp: Literal[1, 2, 3, 4], raw_bytes: bytes):
    self.width = width
    self.height = height
    self.bpp: Literal[1, 2, 3, 4] = bpp
    self.raw_bytes = raw_bytes

  def get_image(self) -> Image.Image:
    bitmap = Image.new("L", (self.width, self.height))
    bits = []
    if self.bpp == 1:
      multiplier = 0xFF
      for byte in self.raw_bytes:
        for i in range(7, -1, -1):
          bits.append((byte >> i) & 0b1)
    elif self.bpp == 2:
      multiplier = 0x55
      for byte in self.raw_bytes:
        for i in range(3, -1, -1):
          bits.append((byte >> 2 * i) & 0b11)
    elif self.bpp == 3:
      multiplier = 0x24
      for pos in range(0, len(self.raw_bytes), 3):
        triple = self.raw_bytes[pos : pos + 3]
        (int_24,) = struct.unpack(">I", b"\0" + triple)
        for i in range(7, -1, -1):
          bits.append((int_24 >> 3 * i) & 0b111)
    elif self.bpp == 4:
      multiplier = 0x11
      for byte in self.raw_bytes:
        for i in range(1, -1, -1):
          bits.append((byte >> 4 * i) & 0b1111)
    else:
      raise ValueError(f"Unsupported bpp: {self.bpp}")

    pos = 0
    for y in range(self.height):
      for x in range(self.width):
        bit = bits[pos]
        pos += 1
        bitmap.putpixel((x, y), 0xFF - bit * multiplier)

    return bitmap

  def get_bytes(self, bitmap: Image.Image) -> bytes:
    if self.bpp == 1:
      multiplier = 0xFF
    elif self.bpp == 2:
      multiplier = 0x55
    elif self.bpp == 3:
      multiplier = 0x24
    elif self.bpp == 4:
      multiplier = 0x11
    else:
      raise ValueError(f"Unsupported bpp: {self.bpp}")

    bits = []
    for y in range(self.height):
      for x in range(self.width):
        pixel: int = bitmap.getpixel((x, y))
        bits.append(round((0xFF - pixel) / multiplier))

    raw_bytes = bytearray()
    if self.bpp == 1:
      bits += [0] * (-len(bits) % 8)
      pos = 0
      while pos < len(bits):
        byte = 0
        for i in range(7, -1, -1):
          byte |= bits[pos] << i
          pos += 1
        raw_bytes.append(byte)
    elif self.bpp == 2:
      bits += [0] * (-len(bits) % 4)
      pos = 0
      while pos < len(bits):
        byte = 0
        for i in range(3, -1, -1):
          byte |= bits[pos] << 2 * i
          pos += 1
        raw_bytes.append(byte)
    elif self.bpp == 3:
      bits += [0] * (-len(bits) % 8)
      pos = 0
      while pos < len(bits):
        triple = 0
        for i in range(7, -1, -1):
          triple |= bits[pos] << 3 * i
          pos += 1
        raw_bytes += struct.pack(">I", triple)[-3:]
    elif self.bpp == 4:
      bits += [0] * (-len(bits) % 2)
      pos = 0
      while pos < len(bits):
        byte = 0
        for i in range(1, -1, -1):
          byte |= bits[pos] << 4 * i
          pos += 1
        raw_bytes.append(byte)
    else:
      raise ValueError(f"Unsupported bpp: {self.bpp}")

    return bytes(raw_bytes)


class CGLP:
  def __init__(self, data: bytes, offset: int = 0, magic_endinaness: Endianess = "<", endianess: Endianess = "<"):
    magic, block_size = struct.unpack_from(f"{endianess}4sI", data, offset)

    if magic_endinaness == ">":
      assert magic == b"CGLP"
    else:
      assert magic == b"PLGC"

    tile_width, tile_height, tile_length, unk, bpp, rotate_mode = struct.unpack_from(
      f"{endianess}2B2H2B", data, offset + 0x08
    )
    self.tile_width: int = tile_width
    self.tile_height: int = tile_height
    assert tile_length == ceil(tile_width * tile_height * bpp / 8)
    self.unk: int = unk
    self.bpp: int = bpp
    self.rotate_mode: int = rotate_mode
    self.tiles: list[CGLPTile] = []
    for i in range(0, (block_size - 0x10) // tile_length):
      self.tiles.append(
        CGLPTile(
          tile_width, tile_height, bpp, data[offset + 0x10 + i * tile_length : offset + 0x10 + (i + 1) * tile_length]
        )
      )

  def get_bytes(self, magic_endinaness: Endianess = "<", endianess: Endianess = "<") -> bytes:
    body = bytearray()
    for tile in self.tiles:
      body += tile.raw_bytes
    body += b"\0" * (-len(body) % 4)

    tile_length = ceil(self.tile_width * self.tile_height * self.bpp / 8)
    head = struct.pack(
      f"{endianess}4sI2B2H2B",
      b"CGLP" if magic_endinaness == ">" else b"PLGC",
      0x10 + len(body),
      self.tile_width,
      self.tile_height,
      tile_length,
      self.unk,
      self.bpp,
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
  def __init__(self, data: bytes, offset: int = 0, magic_endinaness: Endianess = "<", endianess: Endianess = "<"):
    magic, block_size = struct.unpack_from(f"{endianess}4sI", data, offset)

    if magic_endinaness == ">":
      assert magic == b"CWDH"
    else:
      assert magic == b"HDWC"

    first_index, last_index, next_offset = struct.unpack_from(f"{endianess}2HI", data, offset + 0x08)
    self.first_index: int = first_index
    self.last_index: int = last_index
    self.cwdh_offset: int = next_offset

    self.info: list[CWDHInfo] = []
    for i in range(0, (block_size - 0x10) // 3):
      start, width, length = struct.unpack_from("<b2B", data, offset + 0x10 + 3 * i)
      self.info.append(CWDHInfo(start, width, length))

  def get_bytes(self, magic_endinaness: Endianess = "<", endianess: Endianess = "<") -> bytes:
    body = bytearray()
    for info in self.info:
      body += info.get_bytes()
    body += b"\0" * (-len(body) % 4)

    head = struct.pack(
      f"{endianess}4sI2HI",
      b"CWDH" if magic_endinaness == ">" else b"HDWC",
      0x10 + len(body),
      self.first_index,
      self.last_index,
      0,
    )
    return bytes(head + body)


class CMAP:
  def __init__(self, data: bytes, offset: int = 0, magic_endinaness: Endianess = "<", endianess: Endianess = "<"):
    magic, block_size = struct.unpack_from(f"{endianess}4sI", data, offset)

    if magic_endinaness == ">":
      assert magic == b"CMAP"
    else:
      assert magic == b"PAMC"

    first_char_code, last_char_code, type_section, unk_1, cmap_offset = struct.unpack_from(
      f"{endianess}4HI",
      data,
      offset + 0x08,
    )

    assert unk_1 == 0

    self.first_char_code: int = first_char_code
    self.last_char_code: int = last_char_code
    self.type_section: int = type_section
    self.cmap_offset: int = cmap_offset

    self.index_map: dict[int, int] = {}
    if self.type_section == 0:
      (first_char_index,) = struct.unpack_from(f"{endianess}H", data, offset + 0x14)
      for i in range(last_char_code - first_char_code + 1):
        char_index = first_char_index + i
        self.index_map[first_char_code + i] = char_index
    elif self.type_section == 1:
      length = last_char_code - first_char_code + 1
      for i in range(length):
        (char_index,) = struct.unpack_from(f"{endianess}H", data, offset + 0x14 + 2 * i)
        if char_index == 0xFFFF:
          continue
        self.index_map[first_char_code + i] = char_index
    elif self.type_section == 2:
      (num_chars,) = struct.unpack_from(f"{endianess}H", data, offset + 0x14)
      for i in range(num_chars):
        char_code, char_index = struct.unpack_from(f"{endianess}2H", data, offset + 0x16 + 4 * i)
        self.index_map[char_code] = char_index

  @property
  def char_map(self) -> dict[int, int]:
    return {v: k for k, v in self.index_map.items()}

  @staticmethod
  def get_blank():
    return CMAP(b"PAMC" + b"\0" * 0x12)

  def get_bytes(
    self, index_map: dict[int, int] | None = None, magic_endinaness: Endianess = "<", endianess: Endianess = "<"
  ):
    if index_map is None:
      index_map = self.index_map
    sorted_keys = sorted(index_map.keys(), key=lambda x: index_map[x])
    body = bytearray()
    if self.type_section == 0:
      for char_code, char_index in index_map.items():
        body += struct.pack(f"{endianess}H", char_index)
        break
    elif self.type_section == 1:
      length = self.last_char_code - self.first_char_code + 1
      for i in range(length):
        char_code = self.first_char_code + i
        char_index = index_map.get(char_code, 0xFFFF)
        body += struct.pack(f"{endianess}H", char_index)
    elif self.type_section == 2:
      body += struct.pack(f"{endianess}H", len(index_map))
      for key in sorted_keys:
        body += struct.pack(f"{endianess}2H", key, index_map[key])

    body += b"\0" * (-len(body) % 4)

    head = struct.pack(
      f"{endianess}4sI4HI",
      b"CMAP" if magic_endinaness == ">" else b"PAMC",
      0x14 + len(body),
      self.first_char_code,
      self.last_char_code,
      self.type_section,
      0,
      0,
    )
    return bytes(head + body)


class NFTR:
  magic_endianess: Endianess
  endianess: Endianess

  def __init__(self, data: bytes):
    self.data = data

    magic = data[:4]
    if magic == b"NFTR":
      magic_endianess = self.magic_endianess = ">"
    elif magic == b"RTFN":
      magic_endianess = self.magic_endianess = "<"
    else:
      raise ValueError(f"Unknown magic: {magic}")

    (bom,) = struct.unpack_from("<H", data, 4)
    if bom == 0xFEFF:
      endianess = self.endianess = "<"
    elif bom == 0xFFFE:
      endianess = self.endianess = ">"
    else:
      raise ValueError(f"Unknown BOM: {bom:04X}")

    version, file_size, block_size, num_blocks = struct.unpack_from(f"{endianess}HI2H", data, 6)

    assert block_size == 0x10

    self.version: int = version
    self.num_blocks: int = num_blocks

    self.finf: FINF = FINF(data, block_size, magic_endianess, endianess)

    self.cglp: CGLP = CGLP(data, self.finf.cglp_offset - 8, magic_endianess, endianess)

    self.cwdhs: list[CWDH] = []
    next_offset = self.finf.cwdh_offset - 8
    while next_offset < len(data):
      cwdh: CWDH = CWDH(data, next_offset, magic_endianess, endianess)
      self.cwdhs.append(cwdh)
      if cwdh.cwdh_offset == 0:
        break
      next_offset = cwdh.cwdh_offset - 8

    self.char_map: dict[int, int] = {}
    self.cmaps: list[CMAP] = []
    next_offset = self.finf.cmap_offset - 8
    while next_offset < len(data):
      cmap: CMAP = CMAP(data, next_offset, magic_endianess, endianess)
      self.cmaps.append(cmap)
      self.char_map.update(cmap.char_map)
      if cmap.cmap_offset == 0:
        break
      next_offset = cmap.cmap_offset - 8

  def get_bytes(self, magic_endinaness: Endianess = "<", endianess: Endianess = "<") -> bytes:
    cmaps = [cmap.get_bytes(magic_endinaness=magic_endinaness, endianess=endianess) for cmap in self.cmaps]
    cwdhs = [cwdh.get_bytes(magic_endinaness=magic_endinaness, endianess=endianess) for cwdh in self.cwdhs]
    cglp = self.cglp.get_bytes(magic_endinaness=magic_endinaness, endianess=endianess)

    self.finf.cglp_offset = 0x18 + self.finf.block_size
    self.finf.cwdh_offset = self.finf.cglp_offset + len(cglp)
    next_offset = self.finf.cmap_offset
    for i, cwdh in enumerate(cwdhs[:-1]):
      next_offset += len(cwdh)
      cwdhs[i] = cwdh[:0x0C] + struct.pack(f"{endianess}I", next_offset) + cwdh[0x10:]

    self.finf.cmap_offset = self.finf.cwdh_offset + sum(len(cwdh) for cwdh in cwdhs)
    next_offset = self.finf.cmap_offset
    for i, cmap in enumerate(cmaps[:-1]):
      next_offset += len(cmap)
      cmaps[i] = cmap[:0x10] + struct.pack(f"{endianess}I", next_offset) + cmap[0x14:]

    finf = self.finf.get_bytes(magic_endinaness=magic_endinaness, endianess=endianess)

    body = finf + cglp + b"".join(cwdhs) + b"".join(cmaps)

    head = struct.pack(
      f"{endianess}4s2HI2H",
      b"NFTR" if magic_endinaness == ">" else b"RTFN",
      0xFEFF,
      self.version,
      0x10 + len(body),
      0x10,
      0x02 + len(cwdhs) + len(cmaps),
    )
    return bytes(head + body)

  @staticmethod
  def compress_cmap(char_map: dict[int, int]) -> list[CMAP]:
    cmaps: list[CMAP] = []
    type_2_index_map: dict[int, int] = {}

    char_index = 0
    char_map_len = len(char_map)
    while char_index < len(char_map):
      char_code = char_map[char_index]

      code_index_diff = char_code - char_index
      window = 0x20
      while (
        char_index + window < char_map_len and char_map[char_index + window] - (char_index + window) == code_index_diff
      ):
        window += 1
      if window > 0x20:
        cmap = CMAP.get_blank()
        cmap.type_section = 0
        cmap.first_char_code = char_code
        cmap.last_char_code = char_map[char_index + window - 1]
        cmap.index_map = {char_map[index]: index for index in range(char_index, char_index + window)}
        cmaps.append(cmap)
        char_index += window
        continue

      window = 0
      while char_index + window < char_map_len and char_map[char_index + window] - char_code <= window * 2:
        if char_index + window > 0 and char_map[char_index + window] - char_map[char_index + window - 1] > 0x10:
          break
        window += 1

      if window > 0x20:
        cmap = CMAP.get_blank()
        cmap.type_section = 1
        cmap.first_char_code = char_code
        cmap.last_char_code = char_map[char_index + window - 1]
        cmap.index_map = {char_map[index]: index for index in range(char_index, char_index + window)}
        cmaps.append(cmap)

        char_index += window
        continue

      type_2_index_map[char_code] = char_index
      char_index += 1
      continue

    cmap = CMAP.get_blank()
    cmap.type_section = 2
    cmap.first_char_code = min(type_2_index_map.values())
    cmap.last_char_code = 0xFFFF
    cmap.index_map = type_2_index_map
    cmaps.append(cmap)

    return cmaps

  @staticmethod
  def from_file(file: str | BufferedReader) -> NFTR:
    if isinstance(file, str):
      with open(file, "rb") as reader:
        data = reader.read()
    else:
      data = file.read()
    return NFTR(data)
