import json
import os
from typing import Callable, TypedDict

from helper import (
  CHAR_TABLE_PATH,
  CHAR_WIDTH_DICT,
  DIR_TEMP_IMPORT,
  DIR_TEXT_FILES,
  DIR_UNPACKED_FILES,
  FONT_REPLACE_DICT,
  char_table_filter,
  get_used_characters,
)
from nftr import NFTR, CGLPTile, CWDHInfo
from PIL import Image, ImageDraw, ImageFont


class FontConfig(TypedDict):
  handle: Callable[[NFTR], NFTR]
  font: str
  size: int
  draw: Callable[[Image.Image, ImageDraw.ImageDraw, ImageFont.FreeTypeFont, str], None]
  width: int
  length: int


def create_font(
  original_root: str,
  output_root: str,
  config_dict: dict[str, FontConfig],
  characters: list[str],
  char_encoder: Callable[[str], int] = ord,
  font_replace_dict: dict[str, str] = {},
  special_char_width: dict[str, int] = {},
) -> None:
  for file_name, config in config_dict.items():
    nftr = NFTR.from_file(f"{original_root}/{file_name}")

    handle = config.get("handle")
    if handle:
      nftr = handle(nftr)

    font = ImageFont.truetype(config["font"], config["size"])
    draw_char = config["draw"]
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

      if code in char_to_index_map:
        continue

      code = char_encoder(char)

      bitmap = Image.new("L", (tile.width, tile.height), 0xFF)
      draw = ImageDraw.Draw(bitmap)
      draw_char(bitmap, draw, font, font_replace_dict.get(char, char))
      new_tile = CGLPTile(tile.width, tile.height, tile.bpp, tile.get_bytes(bitmap))

      char_width = special_char_width.get(char, config["width"])
      char_length = config.get("length", char_width)

      if code in char_to_index_map:
        _ = char_to_index_map[code]
        nftr.cglp.tiles[_] = new_tile
        nftr.cwdhs[0].info[_].width = char_width
      else:
        index = len(nftr.cglp.tiles)
        char_map[index] = code
        nftr.cglp.tiles.append(new_tile)
        nftr.cwdhs[0].info.append(CWDHInfo(0, char_width, char_length))

    sorted_tiles: list[CGLPTile] = []
    sorted_infos: list[CWDHInfo] = []
    sorted_char_map = {}
    index = 0
    for old_index, code in sorted(char_map.items(), key=lambda x: x[1]):
      sorted_char_map[index] = code
      sorted_tiles.append(nftr.cglp.tiles[old_index])
      sorted_infos.append(nftr.cwdhs[0].info[old_index])
      index += 1

    nftr.cglp.tiles = sorted_tiles
    nftr.cwdhs[0].info = sorted_infos
    char_map = sorted_char_map

    nftr.cmaps = NFTR.compress_cmap(char_map)
    nftr.char_map = char_map

    new_bytes = nftr.get_bytes()
    output_path = f"{output_root}/{file_name}"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as writer:
      writer.write(new_bytes)

    print(f"Saved font {file_name} ({len(char_map):4d} characters, {len(new_bytes) / 1024:2.2f} KiB)")


if __name__ == "__main__":
  version = os.environ.get("XZ_MKDS_VERSION", "normal")

  def handle_middle_font(nftr: NFTR) -> NFTR:
    nftr.cwdhs[0].info[0].length = 1
    nftr.cwdhs[0].info[0].start = 1

    return nftr

  def handle_mario_font(nftr: NFTR) -> NFTR:
    nftr.cwdhs[0].info[0].length = 1
    nftr.cwdhs[0].info[0].start = 1

    return nftr

  def remove_unused_characters_for_dlp(nftr: NFTR) -> NFTR:
    new_char_map = {}
    for index, code in nftr.char_map.items():
      if not char_table_filter(code):
        new_char_map[index] = code

    nftr.char_map = new_char_map
    if nftr.cglp.tile_height > 10:
      nftr.finf.line_height = 10
      nftr.cglp.tile_height = 10
      for tile in nftr.cglp.tiles:
        old_bitmap = tile.get_image()
        new_bitmap = old_bitmap.crop((0, 1, 9, 11))
        tile.height = 10
        tile.raw_bytes = tile.get_bytes(new_bitmap)

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
    y = 9
    if version == "dlp":
      y = 8
    draw.text(
      (0, y),
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

  font_config: dict[str, FontConfig] = {
    "Main2D/LC_Font_m.NFTR": {
      "handle": handle_mario_font,
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
      "handle": handle_mario_font,
      "font": "files/fonts/Zfull-GB.ttf",
      "size": 10,
      "draw": draw_char_mario,
      "width": 11,
    },
  }
  if version == "dlp":
    font_config: dict[str, FontConfig] = {
      "Main2D/LC_Font_s.NFTR": {
        "handle": remove_unused_characters_for_dlp,
        "font": "files/fonts/Zfull-GB.ttf",
        "size": 10,
        "draw": draw_char_s,
        "width": 9,
      },
    }

  with open(CHAR_TABLE_PATH, "r", -1, "utf8") as reader:
    char_table: dict[str, str] = json.load(reader)

  create_font(
    DIR_UNPACKED_FILES,
    DIR_TEMP_IMPORT,
    font_config,
    list(char_table.keys()),
    ord,
    {**char_table, **FONT_REPLACE_DICT},
    CHAR_WIDTH_DICT,
  )

  if version == "dlp":
    font_config_dlp: dict[str, FontConfig] = {
      "Static2D/MBChild_ja.NFTR": {
        "handle": remove_unused_characters_for_dlp,
        "font": "files/fonts/Zfull-GB.ttf",
        "size": 10,
        "draw": draw_char_s,
        "width": 9,
      },
    }
    real_characters = get_used_characters(f"{DIR_TEXT_FILES}/zh_Hans/Static2D")
    characters = [k for k, v in char_table.items() if v in real_characters]
    create_font(
      DIR_UNPACKED_FILES,
      DIR_TEMP_IMPORT,
      font_config_dlp,
      characters,
      ord,
      {**char_table, **FONT_REPLACE_DICT},
      CHAR_WIDTH_DICT,
    )
