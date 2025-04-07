import os
import ndspy.fnt
import ndspy.lz10
import ndspy.narc

from helper import DIR_DATA, DIR_ORIGINAL_FILES, DIR_UNPACKED_FILES, enumrate_narc_files


def unpack_carc(input_root: str, output_root: str):
  for root, dirs, files in os.walk(input_root):
    for file in files:
      if not file.endswith(".carc"):
        continue

      input_path = f"{root}/{file}"
      relative_path = os.path.relpath(input_path, input_root).replace("\\", "/")
      with open(input_path, "rb") as reader:
        raw_bytes = ndspy.lz10.decompress(reader.read())

      narc = ndspy.narc.NARC(raw_bytes)
      for i, file_name in enumrate_narc_files(narc.filenames):
        full_path = f"{output_root}/{relative_path[:-5]}/{file_name}"
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as writer:
          writer.write(narc.files[i])


if __name__ == "__main__":
  unpack_carc(f"{DIR_ORIGINAL_FILES}/{DIR_DATA}", DIR_UNPACKED_FILES)
