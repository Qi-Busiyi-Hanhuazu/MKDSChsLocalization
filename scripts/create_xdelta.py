import os

import pyxdelta
from helper import DIR_ORIGINAL_FILES, DIR_OUT, DIR_OUT_WIFI, DIR_TEMP_OUT


def create_xdelta(original_root: str, modified_root: str, output_root: str):
  for root, dirs, files in os.walk(modified_root):
    dirs[:] = [name for name in dirs if os.path.abspath(f"{root}/{name}") != os.path.abspath(f"{output_root}/xdelta")]
    for file in files:
      file_path = os.path.relpath(f"{root}/{file}", modified_root)
      output_path = f"{output_root}/xdelta/{file_path}"
      os.makedirs(os.path.dirname(output_path), exist_ok=True)
      if not pyxdelta.run(f"{original_root}/{file_path}", f"{modified_root}/{file_path}", output_path):
        raise RuntimeError(f"Failed to create the patch for {modified_root}/{file_path}")


if __name__ == "__main__":
  if os.environ.get("XZ_MKDS_WIFI_TRACKS") == "1":
    create_xdelta(DIR_TEMP_OUT, DIR_OUT_WIFI, DIR_OUT_WIFI)
  else:
    create_xdelta(DIR_ORIGINAL_FILES, DIR_TEMP_OUT, DIR_OUT)
