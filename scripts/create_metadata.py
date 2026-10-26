import json
import os
import subprocess

from helper import DIR_OUT, DIR_OUT_WIFI

if __name__ == "__main__":
  with open("files/metadata.json", "r", -1, "utf8") as reader:
    metadata = json.load(reader)

  metadata["version"] = os.environ.get("XZ_PATCH_VERSION")
  if not metadata["version"]:
    metadata["version"] = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], encoding="utf8").strip()
    if subprocess.check_output(["git", "status", "--porcelain"], encoding="utf8"):
      metadata["version"] += "-dirty"
    metadata["isBeta"] = True

  output_root = DIR_OUT
  if os.environ.get("XZ_MKDS_WIFI_TRACKS") == "1":
    output_root = DIR_OUT_WIFI
    metadata["id"] += "-wifi-tracks"
    metadata["name"] += " Wi-Fi 赛道追加补丁"

  with open(f"{output_root}/metadata.json", "w", -1, "utf8", None, "\n") as writer:
    json.dump(metadata, writer, ensure_ascii=False, indent=2)
