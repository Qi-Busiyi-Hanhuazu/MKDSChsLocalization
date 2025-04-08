import json
import os
import re
from typing import TypedDict

import ndspy.fnt

DIR_TEXT_FILES = "texts"
DIR_ORIGINAL_FILES = "original_files"
DIR_OUT = "out"
DIR_ARM9_PATCH = "arm9_patch"

DIR_DATA = "data/data"
DIR_FONT_FILES = "files/fonts"
DIR_UNPACKED_FILES = "unpacked"
DIR_TEMP_IMPORT = "temp/import"

BANNER_PATH = "original_files/banner.bin"
BANNER_OUT_PATH = "out/banner.bin"

TRASH_PATTERN = re.compile(r"^[\-\. ]*$", re.DOTALL)
CONTROL_PATTERN = re.compile(r"\^[0-9A-Za-z]|%[ds]|~[CFcf][0-9\-]+")
KANA_PATTERN = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]+")

CHINESE_TO_JAPANESE = {
  " ": "　",
  "·": "・",
}
FONT_REPLACE_CHAR = {}
DUPLICATE_FILES = {
  "Scene/MenuDL_ja/ghost.bmg": "Scene/Ghost_ja/ghost.bmg",
  "Scene/Record_ja/ghost.bmg": "Scene/Ghost_ja/ghost.bmg",
  "Scene/Nickname_ja/mission.bmg": "Scene/Logo_ja/mission.bmg",
  "Scene/MenuDL_ja/rule.bmg": "Scene/Menu_ja/rule.bmg",
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


def half_to_full(char: str) -> str:
  char = CHINESE_TO_JAPANESE.get(char, char)
  return char


def enumrate_narc_files(folder: ndspy.fnt.Folder, prefix: str = ""):
  for i, file_name in enumerate(folder.files):
    yield i + folder.firstID, prefix + file_name
  for folder_name, folder in folder.folders:
    yield from enumrate_narc_files(folder, prefix + folder_name + "/")
