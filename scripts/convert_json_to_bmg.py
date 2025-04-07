import io
import os

import ndspy.bmg


from helper import (
  CHINESE_TO_JAPANESE,
  DIR_TEMP_IMPORT,
  DIR_TEXT_FILES,
  DIR_UNPACKED_FILES,
  load_translation_dict,
)


def to_bmg(reader: io.BytesIO, sheet_name: str, data: dict[str, str]) -> bytes:
  bmg = ndspy.bmg.BMG(reader.read())

  for i, message in enumerate(bmg.messages):
    key = f"{sheet_name.replace('/', '_')}_{i:04d}"
    text = data.get(key, "")
    if not text:
      continue

    string_parts = []
    char_pos = 0
    while char_pos < len(text):
      char = text[char_pos]
      if char != "[":
        string_parts.append(CHINESE_TO_JAPANESE.get(char, char))
        char_pos += 1
        continue

      control_end = text.find("]", char_pos)
      if control_end == -1:
        raise ValueError(f"Missing closing bracket in {text}")

      control_type, control_data = text[char_pos + 1 : control_end].split(":", 1)
      string_parts.append(ndspy.bmg.Message.Escape(int(control_type), bytes.fromhex(control_data)))
      char_pos = control_end + 1

    message.stringParts = string_parts

  return bmg.save()


def convert_json_to_bmg(input_root: str, json_root: str, language: str, output_root: str):
  for root, dirs, files in os.walk(f"{json_root}/ja"):
    for file_name in files:
      if not file_name.endswith(".json"):
        continue

      file_path = os.path.relpath(f"{root}/{file_name}", f"{json_root}/ja")
      sheet_name = file_path.removesuffix(".json").replace("\\", "/")
      original_json_path = f"{json_root}/ja/{file_path}"
      translation_json_path = f"{json_root}/{language}/{file_path}"
      if not os.path.exists(original_json_path) or not os.path.exists(translation_json_path):
        continue

      translation_dict = load_translation_dict(translation_json_path)

      with open(f"{input_root}/{sheet_name}.bmg", "rb") as reader:
        new_bytes = to_bmg(reader, sheet_name, translation_dict)

      output_path = f"{output_root}/{sheet_name}.bmg"
      os.makedirs(os.path.dirname(output_path), exist_ok=True)
      with open(output_path, "wb") as writer:
        writer.write(new_bytes)


if __name__ == "__main__":
  convert_json_to_bmg(DIR_UNPACKED_FILES, DIR_TEXT_FILES, "zh_Hans", DIR_TEMP_IMPORT)
