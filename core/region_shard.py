import re
import os
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def region_shard_func():
    # Finds ShooterGameLog
    sgl_loc = rf"{os.getenv("LOCALAPPDATA")}\VALORANT\Saved\Logs\ShooterGame.log"
    if os.path.exists(Path(rf'{sgl_loc}')):
        sgl_path = Path(rf'{sgl_loc}')

        # Reads Lockfile
        sgl_read = open(sgl_path, "r")
        sgl_data = sgl_read.read()
        sgl_read.close()

        # Finds endpoint that contains region and shard
        endpoint = re.search("https://glz-(.+?)-1.(.+?).a.pvp.net", sgl_data)
        region = endpoint.group()[12:14]
        shard = endpoint.group()[17:19]
        print(region)
        print(shard)

        data = {"region": region, "shard": shard}
        return data