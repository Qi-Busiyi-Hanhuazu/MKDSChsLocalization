import json
import os
import struct
from typing import Any, Generator

from helper import (
  CHAR_TABLE_PATH,
  DIR_TEXT_FILES,
  char_table_filter,
  get_used_characters,
)


def generate_unicode() -> Generator[tuple[int, str], Any, None]:
  for high in range(0x4E, 0x9F):
    for low in range(0x00, 0x100):
      code = (high << 8) | low

      try:
        char = struct.pack(">H", code).decode("utf-16-be")

      except UnicodeDecodeError:
        continue
      yield code, char


def generate_char_table(json_root: str) -> dict[str, str]:
  characters = sorted(get_used_characters(json_root))
  generator = generate_unicode()

  char_table = {}

  for char in characters:
    if not char_table_filter(ord(char)):
      char_table[char] = char
    else:
      unicode_code, unicode_char = next(generator)
      char_table[unicode_char] = char

  return char_table


if __name__ == "__main__":
  char_table = generate_char_table(f"{DIR_TEXT_FILES}/zh_Hans")
  os.makedirs(os.path.dirname(CHAR_TABLE_PATH), exist_ok=True)
  with open(CHAR_TABLE_PATH, "w", -1, "utf8") as writer:
    json.dump(char_table, writer, ensure_ascii=False, indent=2)
  print(f"Collected {len(char_table)} characters.")
