import os
import struct

import ndspy._common
from helper import BANNER_OUT_PATH, BANNER_PATH


def edit_banner(input_path: str, output_path: str, new_text: str):
  with open(input_path, "rb") as reader:
    data = reader.read()

  new_text_bytes = new_text.encode("utf-16-le")
  new_text_bytes = new_text_bytes + b"\0" * (0x100 - len(new_text_bytes))

  for pos in range(0x240, 0x840, 0x100):
    data = data[:pos] + new_text_bytes + data[pos + 0x100 :]

  crc16 = ndspy._common.crc16(data[0x20:0x840])
  data = data[:0x02] + struct.pack("<H", crc16) + data[0x04:]

  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  with open(output_path, "wb") as writer:
    writer.write(data)


edit_banner(BANNER_PATH, BANNER_OUT_PATH, "马力欧卡丁车DS\nNintendo")
