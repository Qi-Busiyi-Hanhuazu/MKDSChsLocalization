import os
from typing import Callable, TypedDict

from helper import (
  ADDITIONAL_CHARACTERS,
  DIR_TEMP_IMPORT,
  DIR_TEXT_FILES,
  DIR_UNPACKED_FILES,
  FONT_REPLACE_DICT,
  get_used_characters,
)
from nftr import CMAP, NFTR, CGLPTile, CWDHInfo
from PIL import Image, ImageDraw, ImageFont


class FontConfig(TypedDict):
  handle: Callable[[NFTR], NFTR]
  font: str
  size: int
  draw: Callable[[Image.Image, ImageDraw.ImageDraw, ImageFont.FreeTypeFont, str], None]
  width: int
  length: int


def remove_unused_characters(nftr: NFTR) -> NFTR:
  new_char_map = {}
  for index, code in nftr.char_map.items():
    if 0x4E00 <= code <= 0x9FFF:
      continue
    new_char_map[index] = code

  nftr.char_map = new_char_map
  return nftr


def draw_char_m(bitmap: Image.Image, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, char: str) -> None:
  x, y = 0, 11
  if char == "，":
    x -= 1
    y += 2
  draw.text(
    (x, y),
    char + "　　黑鼠龙龟",
    0x00,
    font,
    "ls",
  )


def draw_char_s(bitmap: Image.Image, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, char: str) -> None:
  draw.text(
    (0, 9),
    char + "　　黑鼠龙龟",
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
    "handle": remove_unused_characters,
    "font": "C:/Windows/Fonts/simsun.ttc",
    "size": 12,
    "draw": draw_char_m,
    "width": 11,
  },
  "Main2D/LC_Font_s.NFTR": {
    "handle": remove_unused_characters,
    "font": "files/fonts/Zfull-GB.ttf",
    "size": 10,
    "draw": draw_char_s,
    "width": 9,
  },
  "Main2D/marioFont.NFTR": {
    "handle": remove_unused_characters,
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


def create_font(
  original_root: str,
  output_root: str,
  config_dict: dict[str, FontConfig],
  characters: list[str],
  char_encoder: Callable[[str], int] = ord,
  font_replace_dict: dict[str, str] = {},
) -> None:
  for file_name, config in config_dict.items():
    nftr = NFTR(f"{original_root}/{file_name}")

    handle = config.get("handle")
    if handle:
      nftr = handle(nftr)

    font = ImageFont.truetype(config["font"], config["size"])
    draw_char = config["draw"]
    char_width = config["width"]
    char_length = config.get("length", char_width)
    nftr.finf.default_start = 0
    nftr.finf.default_width = config["width"]
    nftr.finf.default_length = config.get("length", config["width"])

    char_map = {}
    char_to_index_map = {}
    for index in sorted(nftr.char_map.keys()):
      char_map[index] = nftr.char_map[index]
      char_to_index_map[nftr.char_map[index]] = index

    tile = nftr.cglp.tiles[0]
    for char in characters:
      code = char_encoder(char)

      bitmap = Image.new("L", (tile.width, tile.height), 0xFF)
      draw = ImageDraw.Draw(bitmap)
      draw_char(bitmap, draw, font, font_replace_dict.get(char, char))
      new_tile = CGLPTile(tile.width, tile.height, tile.depth, tile.get_bytes(bitmap))

      if code in char_to_index_map:
        _ = char_to_index_map[code]
        nftr.cglp.tiles[_] = new_tile
        nftr.cwdh.info[_].width = char_width
      else:
        index += 1
        char_map[index] = code
        nftr.cglp.tiles.append(new_tile)
        nftr.cwdh.info.append(CWDHInfo(0, char_width, char_length))

    sorted_tiles: list[CGLPTile] = []
    sorted_infos: list[CWDHInfo] = []
    sorted_char_map = {}
    index = 0
    for old_index, code in sorted(char_map.items(), key=lambda x: x[1]):
      sorted_char_map[index] = code
      sorted_tiles.append(nftr.cglp.tiles[old_index])
      sorted_infos.append(nftr.cwdh.info[old_index])
      index += 1

    nftr.cglp.tiles = sorted_tiles
    nftr.cwdh.info = sorted_infos
    char_map = sorted_char_map

    nftr.cmaps = compress_cmap(char_map)
    nftr.char_map = char_map

    new_bytes = nftr.get_bytes()
    output_path = f"{output_root}/{file_name}"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as writer:
      writer.write(new_bytes)

    print(f"Saved font {file_name} ({len(char_map):4d} characters, {len(new_bytes) / 1024:2.2f} KiB)")


if __name__ == "__main__":
  used_characters = get_used_characters(f"{DIR_TEXT_FILES}/zh_Hans")
  characters = sorted(list(filter(lambda x: 0x4E00 <= ord(x) <= 0x9FFF, used_characters)) + list(ADDITIONAL_CHARACTERS))

  create_font(DIR_UNPACKED_FILES, DIR_TEMP_IMPORT, FONT_CONFIG, characters, ord, FONT_REPLACE_DICT)
