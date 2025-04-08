import os
from typing import Callable

from helper import (
  DIR_TEMP_IMPORT,
  DIR_TEXT_FILES,
  DIR_UNPACKED_FILES,
  FONT_REPLACE_CHAR,
  get_used_characters,
)
from nftr import CMAP, NFTR, CGLPTile, CWDHInfo
from PIL import Image, ImageDraw, ImageFont


def expand_font(old_font: NFTR) -> NFTR:
  old_font.cglp.depth = 1
  old_font.cglp.tile_width = 12
  for tile in old_font.cglp.tiles:
    old_bitmap = tile.get_image()
    new_bitmap = Image.new("L", (12, 16), 0xFF)
    new_bitmap.paste(old_bitmap, (0, 0))
    tile.width = 12
    tile.depth = 1
    tile.raw_bytes = tile.get_bytes(new_bitmap)

  return old_font


def draw_char_m(bitmap: Image.Image, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, char: str) -> None:
  draw.text(
    (0, 11),
    char,
    0x00,
    font,
    "ls",
  )


def draw_char_s(bitmap: Image.Image, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, char: str) -> None:
  draw.text(
    (0, 9),
    char,
    0x00,
    font,
    "ls",
  )


def draw_char_mario(bitmap: Image.Image, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, char: str) -> None:
  draw.fontmode = "1"
  for y in (-1, 1, 0):
    for x in (-1, 1, 0):
      color = 0xAA if (x == 0 and y == 0) else 0x55
      draw.text(
        (1 + x, 10 + y),
        char + "　　黑鼠龙龟",
        color,
        font,
        "ls",
      )


FONT_CONFIG: dict[str, dict] = {
  "Main2D/LC_Font_m.NFTR": {
    "font": "C:/Windows/Fonts/simsun.ttc",
    "size": 12,
    "draw": draw_char_m,
    "width": 11,
  },
  "Main2D/LC_Font_s.NFTR": {
    "font": "files/fonts/Zfull-GB.ttf",
    "size": 10,
    "draw": draw_char_s,
    "width": 9,
  },
  "Main2D/marioFont.NFTR": {
    "font": "files/fonts/Zfull-GB.ttf",
    "size": 10,
    "draw": draw_char_mario,
    "width": 11,
  },
}


def compress_cmap(char_map: dict[int, int]) -> list[CMAP]:
  char_map = {k: v for k, v in char_map.items()}

  cmaps = []
  type_2_index_map = {}

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


def create_font():
  for file_name, config in FONT_CONFIG.items():
    characters = sorted(get_used_characters(f"{DIR_TEXT_FILES}/zh_Hans"))
    nftr = NFTR(f"{DIR_UNPACKED_FILES}/{file_name}")

    handle: Callable[[NFTR], NFTR] = config.get("handle")
    if handle:
      nftr = handle(nftr)

    font = ImageFont.truetype(config["font"], config["size"])
    draw_char: Callable[[Image.Image, ImageDraw.ImageDraw, ImageFont.FreeTypeFont, str], None] = config["draw"]
    char_width: int = config["width"]
    char_length: int = config.get("length", char_width)
    nftr.finf.default_start = 0
    nftr.finf.default_width = config["width"]
    nftr.finf.default_length = config.get("length", config["width"])

    new_char_map = {}
    for code in sorted(nftr.char_map.keys()):
      new_char_map[code] = nftr.char_map[code]

    tile = nftr.cglp.tiles[0]
    for chs in characters:
      if not (chs in characters and (0x4E00 <= ord(chs) <= 0x9FFF or 0x3400 <= ord(chs) <= 0x4DBF)):
        continue

      code += 1
      new_char_map[code] = ord(chs)

      bitmap = Image.new("L", (tile.width, tile.height), 0xFF)
      draw = ImageDraw.Draw(bitmap)
      draw_char(bitmap, draw, font, FONT_REPLACE_CHAR.get(chs, chs))
      new_tile = CGLPTile(tile.width, tile.height, tile.depth, tile.get_bytes(bitmap))

      nftr.cglp.tiles.append(new_tile)
      nftr.cwdh.info.append(CWDHInfo(0, char_width, char_length))

    new_tiles: list[CGLPTile] = []
    new_infos: list[CWDHInfo] = []
    new_new_char_map = {}
    code = 0
    for old_code, char in sorted(new_char_map.items(), key=lambda x: x[1]):
      new_new_char_map[code] = char
      new_tiles.append(nftr.cglp.tiles[old_code])
      new_infos.append(nftr.cwdh.info[old_code])
      code += 1

    nftr.cglp.tiles = new_tiles
    nftr.cwdh.info = new_infos
    new_char_map = new_new_char_map

    nftr.cmaps = compress_cmap(new_char_map)
    nftr.char_map = new_char_map

    new_bytes = nftr.get_bytes()
    os.makedirs(os.path.dirname(f"{DIR_TEMP_IMPORT}/{file_name}"), exist_ok=True)
    with open(f"{DIR_TEMP_IMPORT}/{file_name}", "wb") as writer:
      writer.write(new_bytes)

    print(f"Saved font {file_name} ({len(new_char_map):4d} characters, {len(new_bytes) / 1024:2.2f} KiB)")


if __name__ == "__main__":
  create_font()
