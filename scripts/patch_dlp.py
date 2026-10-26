import hashlib
import hmac
import json
import os
import struct

from helper import (
  BANNER_OUT_PATH,
  DIR_ARM9_BUILD,
  DIR_ORIGINAL_FILES,
  DIR_TEMP_OUT,
  DIR_TEMP_WIFI,
  compile_patch,
  compile_patches,
  elf_symbols,
)
from ndspy import fnt, lz10
from ndspy._common import crc16
from ndspy.bmg import BMG
from ndspy.code import MainCodeFile, Overlay, loadOverlayTable
from ndspy.fnt import Folder
from ndspy.narc import NARC
from nftr import NFTR

DIR_STATION_FILES = f"{DIR_ORIGINAL_FILES}/station"
ARM9_BASE = 0x02000000
RELAY_BASE = 0x021CA4E0
DLP_BASE = RELAY_BASE + 0x800
DOWNLOAD_OVERLAY_BSS = 0x58000
MBCHILD_ARCHIVE_OFFSET = 0x169880
MBCHILD_ARCHIVE_CAPACITY = 0x138C
DLP_FILES = ("stage1.srl", "demomenu", "rom0000d")


def align(value: int, boundary: int = 0x200) -> int:
  return (value + boundary - 1) & -boundary


def u32(data: bytes, offset: int) -> int:
  return struct.unpack_from("<I", data, offset)[0]


def put(data: bytearray, offset: int, value: int):
  struct.pack_into("<I", data, offset, value)


def overlay_digest(table: bytes, key: bytes) -> bytes:
  # SDK overlay-table mode clears words 6 and 14 of every SHA-1 block,
  # including the HMAC pads. Tables consist of complete 32-byte entries.
  def masked(data: bytes) -> bytes:
    result = bytearray(data)
    for offset in range(24, len(result), 32):
      result[offset : offset + 4] = b"\0" * 4
    return bytes(result)

  inner = hashlib.sha1(masked(bytes(byte ^ 0x36 for byte in key)) + masked(table)).digest()
  return hashlib.sha1(masked(bytes(byte ^ 0x5C for byte in key)) + inner).digest()


def patch_overlay_digest(main: bytearray, table: bytes, overlays: dict[int, bytes]):
  digest = overlay_digest(table, bytes(main[0x152CA4:0x152CE4]))
  main[0x16F35C:0x16F370] = digest
  for index, overlay in overlays.items():
    digest = hmac.new(bytes(main[0x152CA4:0x152CE4]), overlay, hashlib.sha1).digest()
    offset = 0x16F370 + index * 20
    main[offset : offset + 20] = digest


def patch_download_heap(main: bytearray, table: bytes):
  end = u32(table, 4) + u32(table, 8) + u32(table, 12)
  compile_patches(main, "downloadSource", defines={"STATION_OVERLAY_END": end})


def patch_parent(arm9: bytes, symbols: dict[str, int], overlay_table: bytes, overlays: dict[int, bytes]) -> bytes:
  code = MainCodeFile(arm9, ARM9_BASE)
  main = bytearray(code.sections[0].data)
  compile_patches(
    main,
    defines={
      f"RELAY_{name.upper()}_ADDRESS": symbols[f"relay_{name}"]
      for name in (
        "mb_init",
        "register",
        "segment_size",
        "parent_callback",
        "scene_update",
      )
    },
  )
  patch_overlay_digest(main, overlay_table, overlays)
  patch_download_heap(main, overlay_table)
  code.sections[0].data = main
  return code.save(compress=True)


def patch_station_overlays(overlays: dict[int, Overlay], payload: bytes, table: bytearray) -> dict[int, bytes]:
  result = {}
  for index in (0, 1):
    overlay = overlays[index]
    # Both host scene paths load one of these overlays. Preserve all original
    # code and BSS addresses, then load the same Station image after either BSS.
    overlay.data.extend(b"\0" * (RELAY_BASE - overlay.ramAddress - len(overlay.data)))
    overlay.data.extend(payload)
    overlay.ramSize = len(overlay.data)
    overlay.bssSize = 0
    result[index] = bytes(overlay.save(compress=True))
    put(table, index * 32 + 8, overlay.ramSize)
    put(table, index * 32 + 12, overlay.bssSize)
    put(table, index * 32 + 28, overlay.compressedSize | (overlay.flags << 24))
  return result


def child_size(arm9: bytes, arm7: bytes) -> int:
  return align(0x400 + len(arm9)) + len(arm7) + 0x88


def localize_mbchild(data: bytes, translated_static: bytes) -> bytes:
  archive = NARC(data)
  translated = NARC(lz10.decompress(translated_static))
  message_name, font_name = "MBChild_ja.bmg", "MBChild_ja.NFTR"
  messages = bytes(translated.getFileByName(message_name))
  text = "".join(part for message in BMG(messages).messages for part in message.stringParts if isinstance(part, str))
  required = {ord(char) for char in text if char not in "\n\r\t"}
  original_font = bytes(archive.getFileByName(font_name))
  font = NFTR(original_font)
  full_font = NFTR(bytes(translated.getFileByName(font_name)))
  missing = sorted(required - set(font.char_map.values()))
  # This font is paired with MBChild's download, disconnect and placeholder
  # messages. Reuse kana slots that none of the translated messages needs.
  slots = [
    index
    for index, code in sorted(font.char_map.items())
    if 0x3040 <= code <= 0x30FF and code not in required and index != font.finf.default_glyph_index
  ]
  full_indexes = {code: index for index, code in full_font.char_map.items()}
  for position, code in enumerate(missing):
    index = slots[position]
    source = full_indexes[code]
    font.cglp.tiles[index] = full_font.cglp.tiles[source]
    font.cwdhs[0].info[index] = full_font.cwdhs[0].info[source]
    font.char_map[index] = code
  # The repository's CMAP writer emits entries in glyph-index order; the
  # game's binary search requires that order to also follow character codes.
  default_code = font.char_map[font.finf.default_glyph_index]
  order = sorted(font.char_map, key=font.char_map.__getitem__)
  font.cglp.tiles = [font.cglp.tiles[index] for index in order]
  font.cwdhs[0].info = [font.cwdhs[0].info[index] for index in order]
  font.char_map = {index: font.char_map[old_index] for index, old_index in enumerate(order)}
  font.finf.default_glyph_index = next(index for index, code in font.char_map.items() if code == default_code)
  font.cmaps = NFTR.compress_cmap(font.char_map)
  localized_font = font.get_bytes()
  for name, replacement in ((message_name, messages), (font_name, localized_font)):
    size = len(archive.getFileByName(name))
    archive.setFileByName(name, replacement.ljust(size, b"\0"))
  return archive.save()


def patch_child_arm9(
  original_arm9: bytes,
  translated_static: bytes,
  overlay_table: bytes,
  overlays: dict[int, bytes],
) -> bytes:
  code = MainCodeFile(original_arm9, ARM9_BASE)
  main = bytearray(code.sections[0].data)
  slot = bytes(main[MBCHILD_ARCHIVE_OFFSET : MBCHILD_ARCHIVE_OFFSET + MBCHILD_ARCHIVE_CAPACITY])
  localized = localize_mbchild(lz10.decompress(slot), translated_static)
  packed = lz10.compress(localized)
  memoryview(main)[MBCHILD_ARCHIVE_OFFSET : MBCHILD_ARCHIVE_OFFSET + len(slot)] = packed.ljust(len(slot), b"\0")
  patch_overlay_digest(main, overlay_table, overlays)
  patch_download_heap(main, overlay_table)
  code.sections[0].data = main
  return code.save(compress=True)


def create_dlp_child(
  header: bytes,
  arm9: bytes,
  arm7: bytes,
  original_arm9: bytes,
) -> bytes:
  arm9 = bytearray(arm9)
  # Reproduce MB_ReadSegment(NULL)'s signed clone image treatment of the secure area.
  arm9[0x1000:0x3000] = b"\0" * 0x2000
  put(arm9, 0xA58, 0xE12FFF1E)
  arm9_offset, arm7_offset = 0x400, align(0x400 + len(arm9))
  result = bytearray(header[:0x200])
  result.extend(b"\0" * (arm9_offset - len(result)))
  result.extend(arm9)
  result.extend(b"\0" * (arm7_offset - len(result)))
  result.extend(arm7)
  result[0x61] |= 0x60
  result[0x62] |= 0x40
  put(result, 0x20, arm9_offset)
  put(result, 0x28, ARM9_BASE)
  put(result, 0x2C, len(arm9))
  put(result, 0x30, arm7_offset)
  put(result, 0x3C, len(arm7))
  helper = compile_patch(
    0x02332C40,
    "childSource/2332C40",
    defines={
      "CLIENT_ARM7_OFFSET": arm7_offset,
      "CLIENT_ARM9_OFFSET": arm9_offset,
      "CLIENT_ARM9_RAM": ARM9_BASE,
      "CLIENT_ARM9_SIZE": len(arm9),
      "CLIENT_GGID": u32(MainCodeFile(original_arm9, ARM9_BASE).sections[0].data, 0x154864),
    },
  )
  result[0x180 : 0x180 + len(helper)] = helper
  put(result, 0x20, 0x180)
  put(result, 0x28, 0x02332C40)
  put(result, 0x2C, 0x100)
  struct.pack_into("<H", result, 0x15E, crc16(result[:0x15E]))
  result.extend(b"\0" * 0x88)
  return bytes(result)


def create_menu(icon: bytes, palette: bytes) -> bytes:
  def field(text: str, size: int) -> bytes:
    raw = text.encode("ascii")
    return raw.ljust(size, b"\0")

  # The signed client expects three rows; blank rows request the same program.
  entries = []
  for i in range(3):
    entry = bytearray(icon if i == 0 else b"\0" * 512)
    entry.extend(palette if i == 0 else b"\0" * 32)
    entry.extend(field("Mario Kart DS" if i == 0 else "", 128))
    entry.extend(field("Nintendo" if i == 0 else "", 128))
    entry.extend(bytes([1, 0x15]))
    entry.extend(b"\0" * (12 * 32))
    entry.extend(field("Touch to download" if i == 0 else "", 32))
    entry.extend(field("", 32))
    entry.extend(b"\0" * 64)
    entry.extend(b"rom0000d\0\0")
    entries.append(entry)
  return b"\x03\0\0\0" + b"".join(entries) + b"\0" * 4


def patch_dlp(resource_root: str):
  with open(f"{DIR_ORIGINAL_FILES}/arm9.bin", "rb") as reader:
    arm9_file = reader.read()
  original_arm9, arm9_post_data = arm9_file[:-12], arm9_file[-12:]
  with open(f"{DIR_ORIGINAL_FILES}/arm7.bin", "rb") as reader:
    arm7 = reader.read()
  with open(f"{DIR_ORIGINAL_FILES}/header.bin", "rb") as reader:
    header = bytearray(reader.read())
  with open(f"{DIR_ORIGINAL_FILES}/fnt.bin", "rb") as reader:
    filenames = fnt.load(reader.read())
  with open(f"{DIR_ORIGINAL_FILES}/fat.json", "r", -1, "utf8") as reader:
    file_sizes = json.load(reader)
  filenames.folders.append(("ds_demo", Folder(files=list(DLP_FILES), firstID=len(file_sizes))))
  file_sizes.extend([0] * len(DLP_FILES))
  for root, dirs, files in os.walk(f"{resource_root}/data"):
    for name in files:
      path = f"{root}/{name}"
      relative = os.path.relpath(path, f"{resource_root}/data").replace("\\", "/")
      file_sizes[filenames.idOf(relative)] = os.path.getsize(path)
  with open(f"{DIR_ORIGINAL_FILES}/overarm9.bin", "rb") as reader:
    table = bytearray(reader.read())

  def read_overlay(overlay_id: int, file_id: int) -> bytes:
    with open(f"{DIR_ORIGINAL_FILES}/overlay/overlay_{overlay_id:04d}.bin", "rb") as reader:
      return reader.read()

  original_overlays = loadOverlayTable(table, read_overlay)
  put(table, 2 * 32 + 12, DOWNLOAD_OVERLAY_BSS)
  service = compile_patch(DLP_BASE, "dlpSource")
  functions = elf_symbols(f"{DIR_ARM9_BUILD}/repl_{DLP_BASE:07X}.elf")
  payload = compile_patch(
    RELAY_BASE,
    "dlpSource/21CA4E0",
    defines={
      f"DLP_{name.upper()}_ADDRESS": functions[f"dlp_{name}"]
      for name in (
        "init",
        "set_info",
        "connect",
        "disconnect",
        "request",
        "update",
        "finish",
        "stop",
      )
    },
  )
  symbols = elf_symbols(f"{DIR_ARM9_BUILD}/repl_{RELAY_BASE:07X}.elf")
  payload = payload.ljust(DLP_BASE - RELAY_BASE, b"\0") + service
  overlays = patch_station_overlays(original_overlays, payload, table)
  for index, overlay in overlays.items():
    file_sizes[original_overlays[index].fileID] = len(overlay)
  with open(f"{resource_root}/data/data/Static2D.carc", "rb") as reader:
    arm9 = patch_child_arm9(original_arm9, reader.read(), table, overlays)
  with open(f"{DIR_STATION_FILES}/ds_demo_client.srl", "rb") as reader:
    station = reader.read()
  with open(f"{DIR_ORIGINAL_FILES}/data/data/Boot/mkds_banner02.nbfc", "rb") as reader:
    icon = reader.read()
  with open(f"{DIR_ORIGINAL_FILES}/data/data/Boot/mkds_banner02.nbfp", "rb") as reader:
    palette = reader.read()
  menu = create_menu(icon, palette)
  child_length = child_size(arm9, arm7)
  file_sizes[-3:] = [len(station), len(menu), child_length]
  parent_arm9 = patch_parent(original_arm9, symbols, table, overlays)
  overlay_file_ids = [overlay.fileID for overlay in original_overlays.values()]
  position = 0x4000 + align(len(parent_arm9) + len(arm9_post_data))
  put(header, 0x50, position)
  position += align(len(table))
  for file_id in overlay_file_ids:
    position += align(file_sizes[file_id])
  position += align(len(arm7))
  names = fnt.save(filenames)
  put(header, 0x40, position)
  put(header, 0x44, len(names))
  position += align(len(names))
  put(header, 0x48, position)
  put(header, 0x4C, len(file_sizes) * 8)
  position += align(len(file_sizes) * 8)
  put(header, 0x68, position)
  position += align(os.path.getsize(BANNER_OUT_PATH))
  for file_id, size in enumerate(file_sizes):
    if file_id not in overlay_file_ids:
      position += align(size)
  position -= align(child_length) - child_length
  put(header, 0x80, align(position, 32))
  files = {
    "stage1.srl": station,
    "demomenu": menu,
    "rom0000d": create_dlp_child(header, arm9, arm7, original_arm9),
  }
  for name, data in files.items():
    path = f"{resource_root}/data/ds_demo/{name}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as writer:
      writer.write(data)

  for name, after in (
    ("arm9.bin", bytes(parent_arm9) + arm9_post_data),
    ("overarm9.bin", bytes(table)),
    *((f"overlay/overlay_{index:04d}.bin", overlay) for index, overlay in overlays.items()),
  ):
    target = f"{resource_root}/{name}"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as writer:
      writer.write(after)


def patch_wifi_arm9(arm9: bytes) -> bytes:
  code = MainCodeFile(arm9, ARM9_BASE)
  main = bytearray(code.sections[0].data)
  compile_patches(main, "wifiSource")
  code.sections[0].data = main
  return bytes(code.save(compress=True))


def wifi_tracks(original_path: str, modified_path: str):
  with open(original_path, "rb") as reader:
    original = reader.read()
  modified = patch_wifi_arm9(original[:-12]) + original[-12:]
  os.makedirs(os.path.dirname(modified_path), exist_ok=True)
  with open(modified_path, "wb") as writer:
    writer.write(modified)


if __name__ == "__main__":
  if os.environ.get("XZ_MKDS_WIFI_TRACKS") == "1":
    wifi_tracks(f"{DIR_TEMP_OUT}/arm9.bin", f"{DIR_TEMP_WIFI}/arm9.bin")
  else:
    patch_dlp(DIR_TEMP_OUT)
