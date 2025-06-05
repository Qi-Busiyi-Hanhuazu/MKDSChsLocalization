import struct

from nitrogfx.convert import NCLR


def nclr_to_act(nclr: NCLR, act_path: str, index: int = 0, bpp: int = 4):
  """Converts NCLR into a ACT palette file
  :param nclr: NCLR
  :param act_path: path to produced palette file
  """
  palette_size = 2**bpp
  with open(act_path, "wb") as pal:
    for c in nclr.colors[index * 16 : palette_size + index * 16]:
      pal.write(struct.pack("BBB", c[0], c[1], c[2]))
    if pal.tell() < 256 * 3:
      pal.write(b"\x00" * (256 * 3 - pal.tell()))
