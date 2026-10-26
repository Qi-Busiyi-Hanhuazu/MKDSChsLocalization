import json
import os

from helper import (
  CHAR_TABLE_PATH,
  DIR_TEXT_FILES,
  get_used_characters,
)

if __name__ == "__main__":
  characters = sorted(get_used_characters(f"{DIR_TEXT_FILES}/zh_Hans"))
  char_table = {k: k for k in characters}
  os.makedirs(os.path.dirname(CHAR_TABLE_PATH), exist_ok=True)
  with open(CHAR_TABLE_PATH, "w", -1, "utf8") as writer:
    json.dump(char_table, writer, ensure_ascii=False, indent=2)
  print(f"Collected {len(char_table)} characters.")
