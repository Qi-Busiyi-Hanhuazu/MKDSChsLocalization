import hashlib
import hmac
import os
import struct
from pathlib import Path

from helper import (
  BANNER_OUT_PATH,
  DIR_ORIGINAL_FILES,
  DIR_OUT_WIFI,
  DIR_TEMP_OUT,
  compile_patch,
  compile_patches,
)
from ndspy import lz10
from ndspy.bmg import BMG
from ndspy.code import MainCodeFile, loadOverlayTable
from ndspy.fnt import Folder
from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom
from nftr import NFTR

DIR_STATION_FILES = f"{DIR_ORIGINAL_FILES}/station"
ROM_PATH = "0228 - Mario Kart DS (Japan).nds"
ORIGINAL_MD5 = "67b9666b1dbaaf1e8ca03bf7786ed5b6"
ARM9_BASE = 0x02000000
RELAY_BASE = 0x021CA4E0
DLP_BASE = RELAY_BASE + 0x800
RELAY_LIMIT = DLP_BASE + 0x2000
ORIGINAL_ARENA_HI = 0x023E0000
ORIGINAL_BSS_END = 0x02180580
DOWNLOAD_OVERLAY_BSS = 0x58000
MBCHILD_ARCHIVE_OFFSET = 0x169880
MBCHILD_ARCHIVE_CAPACITY = 0x138C
STATION_FILES = {
  "ds_demo_client.srl": (306824, "deaec313106e34d8290b4c9c6e3405b8bb2eaec1db6c2cad38ee2771aef1ca2b"),
}
DLP_FILES = ("stage1.srl", "demomenu", "rom0000d")


def align(value: int, boundary: int = 0x200) -> int:
  return (value + boundary - 1) & -boundary


def crc16(data: bytes) -> int:
  value = 0xFFFF
  for byte in data:
    value ^= byte
    for _ in range(8):
      value = (value >> 1) ^ (0xA001 if value & 1 else 0)
  return value


def u32(data: bytes, offset: int) -> int:
  return struct.unpack_from("<I", data, offset)[0]


def put(data: bytearray, offset: int, value: int):
  struct.pack_into("<I", data, offset, value)


def checked(data: bytearray, address: int, before: bytes, after: bytes):
  offset = address - ARM9_BASE
  if data[offset : offset + len(before)] != before:
    raise ValueError(f"ARM9 input differs at {address:08x}; expected Japanese AMCJ revision 0")
  if len(before) != len(after):
    raise ValueError("An in-place hook must keep its original size")
  data[offset : offset + len(after)] = after


def overlay_digest(table: bytes, key: bytes) -> bytes:
  # SDK overlay-table mode clears words 6 and 14 of every SHA-1 block,
  # including the HMAC pads. Tables consist of complete 32-byte entries.
  if len(table) % 32 or len(key) != 64:
    raise ValueError("Unexpected overlay table or digest key size")

  def masked(data: bytes) -> bytes:
    result = bytearray(data)
    for offset in range(24, len(result), 32):
      result[offset : offset + 4] = b"\0" * 4
    return bytes(result)

  inner = hashlib.sha1(masked(bytes(byte ^ 0x36 for byte in key)) + masked(table)).digest()
  return hashlib.sha1(masked(bytes(byte ^ 0x5C for byte in key)) + inner).digest()


def patch_overlay_digest(main: bytearray, table: bytes, overlays: dict[int, bytes]):
  digest = overlay_digest(table, bytes(main[0x152CA4:0x152CE4]))
  checked(main, 0x0216F35C, bytes.fromhex("23dda6b6a2c117e415c167967cdb98388395ceea"), digest)
  for index, overlay in overlays.items():
    digest = hmac.new(bytes(main[0x152CA4:0x152CE4]), overlay, hashlib.sha1).digest()
    before = ("0140b3a21dd073401fd277bcbec65cdecc9d0431", "c95d468535f829010b2a003a3862e8f8c58f1f47")[index]
    checked(main, 0x0216F370 + index * 20, bytes.fromhex(before), digest)


def patch_download_heap(main: bytearray, table: bytes):
  end = u32(table, 4) + u32(table, 8) + u32(table, 12)
  compile_patches(main, "downloadSource", defines={"STATION_OVERLAY_END": end})


def patch_parent(arm9: bytes, symbols: dict[str, int], overlay_table: bytes, overlays: dict[int, bytes]) -> bytes:
  code = MainCodeFile(arm9, ARM9_BASE)
  main = bytearray(code.sections[0].data)
  settings = code.codeSettingsOffs
  if settings != 0xB4C or u32(main, settings + 0x10) != ORIGINAL_BSS_END:
    raise ValueError("Unexpected AMCJ code settings or BSS boundary")
  compile_patches(
    main,
    defines={
      f"RELAY_{name.upper()}_ADDRESS": symbols[f"relay_{name}"]
      for name in ("mb_init", "register", "segment_size", "parent_callback", "scene_update")
    },
  )
  patch_overlay_digest(main, overlay_table, overlays)
  patch_download_heap(main, overlay_table)
  code.sections[0].data = main
  return code.save(compress=True)


def patch_station_overlays(original: NintendoDSRom, payload: bytes, table: bytearray) -> dict[int, bytes]:
  if not payload or len(payload) > RELAY_LIMIT - RELAY_BASE:
    raise ValueError("Station exceeds its overlay load window")
  overlays = loadOverlayTable(original.arm9OverlayTable, lambda overlay_id, file_id: original.files[file_id])
  result = {}
  for index in (0, 1):
    overlay = overlays[index]
    end = overlay.ramAddress + overlay.ramSize + overlay.bssSize
    if end > RELAY_BASE or RELAY_BASE + len(payload) > u32(table, 2 * 32 + 4) + 32 + DOWNLOAD_OVERLAY_BSS:
      raise ValueError("Station overlaps the original overlay image or exceeds its reserved region")
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
  if (
    (font.cglp.tile_width, font.cglp.tile_height, font.cglp.bpp)
    != (
      full_font.cglp.tile_width,
      full_font.cglp.tile_height,
      full_font.cglp.bpp,
    )
    or len(font.cwdhs) != 1
    or len(full_font.cwdhs) != 1
  ):
    raise ValueError("Unexpected embedded MBChild font layout")
  missing = sorted(required - set(font.char_map.values()))
  # This font is paired with MBChild's download, disconnect and placeholder
  # messages. Reuse kana slots that none of the translated messages needs.
  slots = [
    index
    for index, code in sorted(font.char_map.items())
    if 0x3040 <= code <= 0x30FF and code not in required and index != font.finf.default_glyph_index
  ]
  if len(missing) > len(slots):
    raise ValueError("MBChild translation exceeds the original font slots")
  full_indexes = {code: index for index, code in full_font.char_map.items()}
  for code, index in zip(missing, slots):
    if code not in full_indexes:
      raise ValueError(f"MBChild translation has no glyph for U+{code:04X}")
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
  if len(localized_font) > len(original_font):
    raise ValueError("Localized MBChild font exceeds its original file slot")
  # Preserve the entire NARC layout, file extents and decompression allocation.
  fnt_offset = 0x10 + u32(data, 0x14)
  image_offset = fnt_offset + u32(data, fnt_offset + 4) + 8
  result = bytearray(data)
  for name, replacement in ((message_name, messages), (font_name, localized_font)):
    file_id = archive.filenames.idOf(name)
    if file_id is None:
      raise ValueError("Unexpected embedded MBChild archive")
    start, end = struct.unpack_from("<2I", data, 0x1C + file_id * 8)
    if len(replacement) > end - start or image_offset + end > len(data):
      raise ValueError(f"Localized {name} exceeds its original NARC file slot")
    result[image_offset + start : image_offset + end] = replacement.ljust(end - start, b"\0")
  return bytes(result)


def patch_child_arm9(
  original: NintendoDSRom, translated_static: bytes, overlay_table: bytes, overlays: dict[int, bytes]
) -> bytes:
  code = MainCodeFile(original.arm9, original.arm9RamAddress)
  main = bytearray(code.sections[0].data)
  slot = bytes(main[MBCHILD_ARCHIVE_OFFSET : MBCHILD_ARCHIVE_OFFSET + MBCHILD_ARCHIVE_CAPACITY])
  localized = localize_mbchild(lz10.decompress(slot), translated_static)
  packed = lz10.compress(localized)
  if len(packed) > len(slot):
    raise ValueError("Translated MBChild archive exceeds its original compressed slot")
  checked(main, ARM9_BASE + MBCHILD_ARCHIVE_OFFSET, slot, packed.ljust(len(slot), b"\0"))
  if u32(main, 0xCAF30) != ARM9_BASE + MBCHILD_ARCHIVE_OFFSET or u32(main, 0xF148) != ORIGINAL_ARENA_HI:
    raise ValueError("Unexpected original client resource pointer or arena limit")
  patch_overlay_digest(main, overlay_table, overlays)
  patch_download_heap(main, overlay_table)
  code.sections[0].data = main
  return code.save(compress=True)


def create_dlp_child(
  header: bytes,
  arm9: bytes,
  arm7: bytes,
  original: NintendoDSRom,
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
  put(result, 0x60, u32(result, 0x60) | 0x406000)
  put(result, 0x20, arm9_offset)
  put(result, 0x24, original.arm9EntryAddress)
  put(result, 0x28, original.arm9RamAddress)
  put(result, 0x2C, len(arm9))
  put(result, 0x30, arm7_offset)
  put(result, 0x34, original.arm7EntryAddress)
  put(result, 0x38, original.arm7RamAddress)
  put(result, 0x3C, len(arm7))
  helper, _ = compile_patch(
    0x02332C40,
    source_folder="childSource",
    defines={
      "CLIENT_ARM7_OFFSET": arm7_offset,
      "CLIENT_ARM9_OFFSET": arm9_offset,
      "CLIENT_ARM9_RAM": original.arm9RamAddress,
      "CLIENT_ARM9_SIZE": len(arm9),
      "CLIENT_GGID": u32(MainCodeFile(original.arm9, original.arm9RamAddress).sections[0].data, 0x154864),
    },
  )
  if len(helper) > 0x100:
    raise ValueError("The Station handoff must fit the 256-byte load window")
  result[0x180 : 0x180 + len(helper)] = helper
  put(result, 0x20, 0x180)
  put(result, 0x28, 0x02332C40)
  put(result, 0x2C, 0x100)
  struct.pack_into("<H", result, 0x15E, crc16(result[:0x15E]))
  result.extend(b"\0" * 0x88)
  return bytes(result)


def check_station_files(files: dict[str, bytes]):
  for name, (size, digest) in STATION_FILES.items():
    data = files.get(name, b"")
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
      raise ValueError(f"Station resource differs: {name}; extract the specified Download Station Volume 1 again")


def load_station(input_root: Path) -> dict[str, bytes]:
  files = {name: (input_root / name).read_bytes() for name in STATION_FILES}
  check_station_files(files)
  return files


def read_resource(rom: NintendoDSRom, name: str) -> bytes:
  return bytes(rom.getFileByName("ds_demo/" + name))


def create_menu(icon: bytes, palette: bytes) -> bytes:
  def field(text: str, size: int) -> bytes:
    raw = text.encode("ascii")
    if len(raw) >= size:
      raise ValueError("Station menu field overflow")
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
    if len(entry) != 1324:
      raise ValueError("Unexpected Station menu record size")
    entries.append(entry)
  return b"\x03\0\0\0" + b"".join(entries) + b"\0" * 4


def patch_dlp(input_path: str, resource_root: str):
  raw = Path(input_path).read_bytes()
  if hashlib.md5(raw).hexdigest() != ORIGINAL_MD5:
    raise ValueError("The source ROM must match the Japanese CRC/MD5 in README.md")
  original = NintendoDSRom(raw)
  rom = NintendoDSRom(raw)
  first_id = len(rom.files)
  rom.filenames.folders.append(("ds_demo", Folder(files=list(DLP_FILES), firstID=first_id)))
  rom.files.extend((Path(DIR_ORIGINAL_FILES) / "data/ds_demo" / name).read_bytes() for name in DLP_FILES)
  rom.sortedFileIds.extend(range(first_id, first_id + len(DLP_FILES)))
  for root, dirs, files in os.walk(f"{resource_root}/data"):
    for name in files:
      path = f"{root}/{name}"
      relative = os.path.relpath(path, f"{resource_root}/data").replace("\\", "/")
      rom.setFileByName(relative, Path(path).read_bytes())
  download_files = ("data/KartModelMainA.carc", "data/KartModelMainB.carc", "data/Main2D.carc", "data/Main2D_ja.carc")
  required = 0x40 + sum(align(len(rom.getFileByName(name)), 32) for name in download_files)
  if required > DOWNLOAD_OVERLAY_BSS:
    raise ValueError("Full translation exceeds the clone-client download heap")
  rom.iconBanner = bytearray(Path(BANNER_OUT_PATH).read_bytes())
  table = bytearray(rom.arm9OverlayTable)
  if u32(table, 2 * 32 + 12) != 0x50000:
    raise ValueError("Unexpected clone-client download overlay size")
  put(table, 2 * 32 + 12, DOWNLOAD_OVERLAY_BSS)
  service, functions = compile_patch(DLP_BASE, sources="dlpSource", host="mkds")
  payload, symbols = compile_patch(
    RELAY_BASE,
    source_folder="dlpSource",
    host="mkds",
    defines={
      f"DLP_{name.upper()}_ADDRESS": functions[f"dlp_{name}"]
      for name in ("init", "set_info", "get_progress", "connect", "disconnect", "request", "update", "finish", "stop")
    },
  )
  if len(payload) > DLP_BASE - RELAY_BASE or len(service) > RELAY_LIMIT - DLP_BASE:
    raise ValueError("Download Play code exceeds its menu overlay load window")
  payload = payload.ljust(DLP_BASE - RELAY_BASE, b"\0") + service
  overlays = patch_station_overlays(original, payload, table)
  for index, overlay in overlays.items():
    rom.files[u32(table, index * 32 + 24)] = overlay
  rom.arm9OverlayTable = table
  arm9 = patch_child_arm9(original, bytes(rom.getFileByName("data/Static2D.carc")), table, overlays)
  station = load_station(Path(DIR_STATION_FILES))
  files = {
    "stage1.srl": station["ds_demo_client.srl"],
    "demomenu": create_menu(
      original.getFileByName("data/Boot/mkds_banner02.nbfc"),
      original.getFileByName("data/Boot/mkds_banner02.nbfp"),
    ),
    "rom0000d": b"\0" * child_size(arm9, original.arm7),
  }
  rom.arm9 = patch_parent(rom.arm9, symbols, table, overlays)
  for name, data in files.items():
    rom.setFileByName("ds_demo/" + name, data)
  packed = rom.save()
  child = create_dlp_child(packed[:0x200], arm9, original.arm7, original)
  if len(child) != len(files["rom0000d"]):
    raise ValueError("Child size changed after fixing the filesystem layout")
  rom.setFileByName("ds_demo/rom0000d", child)
  if rom.save()[0x40:0x50] != child[0x40:0x50]:
    raise ValueError("Parent FAT/FNT layout moved after building the child")
  for name in DLP_FILES:
    path = Path(resource_root) / "data/ds_demo" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(read_resource(rom, name))

  for name, before, after in (
    ("arm9.bin", bytes(original.arm9) + original.arm9PostData, bytes(rom.arm9) + rom.arm9PostData),
    ("overarm9.bin", bytes(original.arm9OverlayTable), bytes(table)),
    *(
      (f"overlay/overlay_{index:04d}.bin", bytes(original.files[index]), overlay) for index, overlay in overlays.items()
    ),
  ):
    source = Path(DIR_ORIGINAL_FILES) / name
    if source.read_bytes() != before:
      raise ValueError(f"Original system file differs from the Japanese ROM: {name}")
    target = Path(resource_root) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(after)


def patch_wifi_arm9(arm9: bytes) -> bytes:
  code = MainCodeFile(arm9, ARM9_BASE)
  main = bytearray(code.sections[0].data)
  if not RELAY_BASE <= u32(main, 0x4B0B0) & ~1 < DLP_BASE:
    raise ValueError("Apply the complete translation patch before the Wi-Fi track add-on")
  compile_patches(main, "wifiSource")
  code.sections[0].data = main
  return bytes(code.save(compress=True))


def wifi_tracks(original_path: str, modified_path: str):
  original = Path(original_path).read_bytes()
  modified = patch_wifi_arm9(original[:-12]) + original[-12:]
  if align(len(modified)) != align(len(original)):
    raise ValueError("ARM9 size changed; recheck the Download Play filesystem layout")
  Path(modified_path).parent.mkdir(parents=True, exist_ok=True)
  Path(modified_path).write_bytes(modified)


if __name__ == "__main__":
  if os.environ.get("XZ_MKDS_WIFI_TRACKS") == "1":
    wifi_tracks(f"{DIR_TEMP_OUT}/arm9.bin", f"{DIR_OUT_WIFI}/arm9.bin")
  else:
    patch_dlp(ROM_PATH, DIR_TEMP_OUT)
