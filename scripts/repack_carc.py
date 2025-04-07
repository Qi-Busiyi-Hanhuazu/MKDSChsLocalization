import os

import ndspy.lz10
import ndspy.narc
from helper import (
  DIR_DATA,
  DIR_ORIGINAL_FILES,
  DIR_OUT,
  DIR_TEMP_IMPORT,
  DUPLICATE_FILES,
  enumrate_narc_files,
)


def repack_carc(input_root: str, replace_root: str, output_root: str):
  for root, dirs, files in os.walk(input_root):
    for file in files:
      if not file.endswith(".carc"):
        continue

      input_path = f"{root}/{file}"
      relative_path = os.path.relpath(input_path, input_root).replace("\\", "/")
      with open(input_path, "rb") as reader:
        raw_bytes = ndspy.lz10.decompress(reader.read())

      narc = ndspy.narc.NARC(raw_bytes)
      changed = False
      for i, file_name in enumrate_narc_files(narc.filenames):
        sub_file_path = f"{relative_path[:-5]}/{file_name}"
        if sub_file_path in DUPLICATE_FILES:
          sub_file_path = DUPLICATE_FILES[sub_file_path]
        full_path = f"{replace_root}/{sub_file_path}"
        if not os.path.exists(full_path):
          continue

        with open(full_path, "rb") as reader:
          narc.files[i] = reader.read()

        changed = True

      if not changed:
        continue

      output_path = f"{output_root}/{relative_path}"
      os.makedirs(os.path.dirname(output_path), exist_ok=True)
      with open(output_path, "wb") as writer:
        writer.write(ndspy.lz10.compress(narc.save()))


if __name__ == "__main__":
  repack_carc(f"{DIR_ORIGINAL_FILES}/{DIR_DATA}", DIR_TEMP_IMPORT, f"{DIR_OUT}/{DIR_DATA}")
