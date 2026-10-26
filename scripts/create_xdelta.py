import os
import shutil

import pyxdelta
from helper import (
  DIR_ORIGINAL_FILES,
  DIR_OUT,
  DIR_OUT_WIFI,
  DIR_TEMP_OUT,
  DIR_TEMP_WIFI,
)


def create_xdelta(original_root: str, modified_root: str, output_root: str):
  for root, dirs, files in os.walk(modified_root):
    for file in files:
      file_path = os.path.relpath(f"{root}/{file}", modified_root)
      if os.path.isfile(f"{original_root}/{file_path}"):
        output_path = f"{output_root}/xdelta/{file_path}"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pyxdelta.run(f"{original_root}/{file_path}", f"{modified_root}/{file_path}", output_path)
      else:
        output_path = f"{output_root}/{file_path}"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copyfile(f"{modified_root}/{file_path}", output_path)


if __name__ == "__main__":
  if os.environ.get("XZ_MKDS_WIFI_TRACKS") == "1":
    create_xdelta(DIR_TEMP_OUT, DIR_TEMP_WIFI, DIR_OUT_WIFI)
  else:
    create_xdelta(DIR_ORIGINAL_FILES, DIR_TEMP_OUT, DIR_OUT)
