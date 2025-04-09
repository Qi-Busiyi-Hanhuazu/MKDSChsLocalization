import math
import os

from helper import DIR_ORIGINAL_FILES, DIR_OUT, DIR_TEMP_OUT

PATCH_FILE_PATH = "data/Boot/builddate.bin"

patch_file_size = 0

for root, dirs, files in os.walk(f"{DIR_TEMP_OUT}/data"):
  for file_name in files:
    path = f"{root}/{file_name}"
    relative_path = os.path.relpath(path, f"{DIR_TEMP_OUT}/data").replace("\\", "/")
    original_path = f"{DIR_ORIGINAL_FILES}/data/{relative_path}"

    if os.path.exists(original_path):
      patch_file_size += math.ceil(os.path.getsize(original_path) / 0x200)

    if relative_path != PATCH_FILE_PATH:
      patch_file_size -= math.ceil(os.path.getsize(path) / 0x200)

output_path = f"{DIR_TEMP_OUT}/data/{PATCH_FILE_PATH}"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "wb") as writer:
  writer.write(b"\x24" * (patch_file_size * 0x200 + 1))
