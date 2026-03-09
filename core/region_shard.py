import os
import re
from pathlib import Path


def region_shard_func():
    sgl_loc = rf"{os.getenv('LOCALAPPDATA')}\VALORANT\Saved\Logs\ShooterGame.log"
    sgl_path = Path(sgl_loc)
    if not sgl_path.exists():
        return None

    with open(sgl_path, "r", encoding="utf-8", errors="ignore") as sgl_read:
        sgl_data = sgl_read.read()

    endpoint = re.search(r"https://glz-(.+?)-1.(.+?).a.pvp.net", sgl_data)
    if endpoint is None:
        return None

    data = {
        "region": endpoint.group()[12:14],
        "shard": endpoint.group()[17:19],
    }
    print(data["region"])
    print(data["shard"])
    return data
