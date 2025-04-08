import os

import pyxdelta
from helper import DIR_ORIGINAL_FILES, DIR_OUT, DIR_TEMP_OUT


def create_xdelta(original_root: str, modified_root: str, output_root: str):
  for root, dirs, files in os.walk(modified_root):
    for file in files:
      file_path = os.path.relpath(f"{root}/{file}", modified_root)
      output_path = f"{output_root}/xdelta/{file_path}"
      os.makedirs(os.path.dirname(output_path), exist_ok=True)
      pyxdelta.run(f"{original_root}/{file_path}", f"{modified_root}/{file_path}", output_path)


if __name__ == "__main__":
  create_xdelta(DIR_ORIGINAL_FILES, DIR_TEMP_OUT, DIR_OUT)
