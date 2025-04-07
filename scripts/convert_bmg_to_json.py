import io
import json
import os

import ndspy.bmg
from helper import (
  DIR_TEXT_FILES,
  DIR_UNPACKED_FILES,
  DUPLICATE_FILES,
  TRASH_PATTERN,
  TranslationItem,
)


def parse_messages(reader: io.BytesIO, sheet_name: str) -> list[TranslationItem]:
  output = []
  bmg = ndspy.bmg.BMG(reader.read())

  for i, message in enumerate(bmg.messages):
    text = str(message)

    item = {
      "index": i,
      "key": f"{sheet_name.replace('/', '_')}_{i:04d}",
      "original": text,
      "translation": text,
    }
    if TRASH_PATTERN.search(text):
      item["trash"] = True
    output.append(item)

  return output


def convert_bmg_to_json(input_root: str, json_root: str, language: str):
  for root, dirs, files in os.walk(input_root):
    for file_name in files:
      lower_file_name = file_name.lower()
      if not lower_file_name.endswith(".bmg"):
        continue
      if any(map(lambda x: x in lower_file_name, ["staffroll", "_es", "_fr", "_ge", "_it", "_us"])):
        continue

      file_path = os.path.relpath(f"{root}/{file_name}", input_root)
      output_path = f"{json_root}/{language}/{file_path.removesuffix('.bmg')}.json"
      sheet_name = file_path.removesuffix(".bmg").replace("\\", "/")

      if f"{sheet_name}.bmg" in DUPLICATE_FILES:
        continue

      with open(f"{input_root}/{file_path}", "rb") as reader:
        parsed = parse_messages(reader, sheet_name)

      if len(parsed) > 0:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", -1, "utf8", None, "\n") as writer:
          json.dump(parsed, writer, ensure_ascii=False, indent=2)
        continue

      if os.path.exists(output_path):
        os.remove(output_path)


if __name__ == "__main__":
  convert_bmg_to_json(DIR_UNPACKED_FILES, DIR_TEXT_FILES, "ja")
