import json
import os
import re
import struct
import subprocess
from pathlib import Path
from typing import TypedDict

import ndspy.fnt

DIR_TEXT_FILES = "texts"
DIR_ORIGINAL_FILES = "original_files"
DIR_OUT = "out"
DIR_OUT_WIFI = f"{DIR_OUT}/wifi_tracks"
DIR_ARM9_PATCH = "arm9_patch"

DIR_DATA = "data/data"
DIR_FONT_FILES = "files/fonts"
DIR_UNPACKED_FILES = "unpacked"
DIR_TEMP_IMPORT = "temp/import"
DIR_TEMP_OUT = "temp/out"

CHAR_TABLE_PATH = "out/char_table.json"
BANNER_PATH = "original_files/banner.bin"
BANNER_OUT_PATH = "out/banner.bin"

TRASH_PATTERN = re.compile(r"^[\-\. ]*$", re.DOTALL)
CONTROL_PATTERN = re.compile(r"\^[0-9A-Za-z]|%[ds]|~[CFcf][0-9\-]+")
KANA_PATTERN = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]+")

CHINESE_TO_JAPANESE = {
  " ": "　",
  "·": "・",
}
FONT_REPLACE_DICT = {
  "\u2005": " ",
}
CHAR_WIDTH_DICT = {
  "\u2005": 9,
}
ADDITIONAL_CHARACTERS = "，：《》"
DUPLICATE_FILES = {
  "Scene/MenuDL_ja/ghost.bmg": "Scene/Ghost_ja/ghost.bmg",
  "Scene/Record_ja/ghost.bmg": "Scene/Ghost_ja/ghost.bmg",
  "Scene/Nickname_ja/mission.bmg": "Scene/Logo_ja/mission.bmg",
  "Scene/MenuDL_ja/rule.bmg": "Scene/Menu_ja/rule.bmg",
  "Scene/MenuDL_ja/common/select_game_s.nce.ncgr": "Scene/Menu_ja/common/select_game_s.nce.ncgr",
}


class TranslationItem(TypedDict):
  index: int
  key: str
  original: str
  translation: str
  suffix: str
  trash: bool
  untranslated: bool
  offset: int
  max_length: int


def load_translation_dict(path: str) -> dict[str, str]:
  with open(path, "r", -1, "utf8") as reader:
    translation_list: list[TranslationItem] = json.load(reader)

  translations = {}
  for item_dict in translation_list:
    if item_dict.get("trash", False):
      continue
    if item_dict.get("untranslated", False) and item_dict["original"] == item_dict["translation"]:
      continue
    translations[item_dict["key"]] = item_dict["translation"]

  return translations


def load_translation_items(path: str) -> list[TranslationItem]:
  with open(path, "r", -1, "utf8") as reader:
    translation_list = json.load(reader)

  return translation_list


def get_used_characters(json_root: str) -> set[str]:
  characters = set()
  for root, dirs, files in os.walk(json_root):
    for file_name in files:
      if not file_name.endswith(".json"):
        continue

      translations = load_translation_dict(f"{root}/{file_name}")

      for key, content in translations.items():
        content = CONTROL_PATTERN.sub("", content).replace("\n", "")
        if KANA_PATTERN.search(content):
          continue

        for k, v in CHINESE_TO_JAPANESE.items():
          content = content.replace(k, v)

        for char in content:
          characters.add(char)

  return characters


def enumrate_narc_files(folder: ndspy.fnt.Folder, prefix: str = ""):
  for i, file_name in enumerate(folder.files):
    yield i + folder.firstID, prefix + file_name
  for folder_name, folder in folder.folders:
    yield from enumrate_narc_files(folder, prefix + folder_name + "/")


def elf_symbols(path: Path) -> dict[str, int]:
  data = path.read_bytes()
  if data[:7] != b"\x7fELF\x01\x01\x01":
    raise ValueError("Expected a little-endian ELF32 file")
  shoff = struct.unpack_from("<I", data, 0x20)[0]
  shsize, count = struct.unpack_from("<2H", data, 0x2E)
  sections = [struct.unpack_from("<10I", data, shoff + i * shsize) for i in range(count)]
  symbols = {}
  for section in sections:
    if section[1] != 2:
      continue
    strings = sections[section[6]]
    text = data[strings[4] : strings[4] + strings[5]]
    for offset in range(section[4], section[4] + section[5], section[9]):
      name_offset, value = struct.unpack_from("<2I", data, offset)
      name = text[name_offset:].split(b"\0", 1)[0].decode("ascii")
      if name:
        symbols[name] = value
  return symbols


def compile_patch(
  address: int,
  source_folder: str = "replSource",
  defines: dict[str, int] | None = None,
  sources: str = "",
  host: str = "",
):
  root = Path(__file__).resolve().parents[1]
  target = f"repl_{address:07X}"
  cppflags = [f"-include hosts/{host}.h"] if host else []
  cppflags.extend(f"-D{name}={value}" for name, value in (defines or {}).items())
  subprocess.run(
    [
      "make",
      "-B",
      f"TARGET={target}",
      f"SOURCES={sources or f'{source_folder}/{address:07X}'}",
      f"CODEADDR=0x{address:07X}",
      "CPPFLAGS=" + " ".join(cppflags),
    ],
    cwd=root / DIR_ARM9_PATCH,
    check=True,
  )
  symbols = elf_symbols(root / DIR_OUT / f"{target}.elf")
  return (root / DIR_OUT / f"{target}.bin").read_bytes(), symbols


def compile_patches(
  binary: bytearray,
  source_folder: str = "replSource",
  defines: dict[str, int] | None = None,
  ram_address: int = 0x02000000,
):
  root = Path(__file__).resolve().parents[1]
  for folder in sorted((root / DIR_ARM9_PATCH / source_folder).iterdir()):
    if not folder.is_dir():
      continue
    address = int(folder.name, 16)
    offset = address - ram_address
    if offset < 0:
      raise ValueError(f"Patch address {address:08x} precedes the binary's RAM address")
    patch, _ = compile_patch(address, source_folder, defines)
    end = offset + len(patch)
    if end > len(binary):
      binary.extend(b"\0" * (end - len(binary)))
    binary[offset:end] = patch
