"""Seed writable caches from the executable without replacing valid user caches."""

import json
from io import BytesIO
import os
from pathlib import Path
import shutil
import sys
import uuid

from PIL import Image
import requests


def valid_image(path):
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError, SyntaxError):
        return False


def valid_metadata(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return isinstance(data, dict) and isinstance(data.get('data'), list) and bool(data['data'])
    except (OSError, ValueError):
        return False


def download_image(url, path):
    target = Path(path)
    for _ in range(2):
        temporary = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.tmp')
        try:
            response = requests.get(url, timeout=(5, 30))
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as image:
                image.verify()
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(response.content)
            os.replace(temporary, target)
            return True
        except (requests.RequestException, OSError, ValueError, SyntaxError):
            pass
        finally:
            temporary.unlink(missing_ok=True)
    return False


def seed_runtime_resources(base_path=None, bundle_path=None):
    if bundle_path is None:
        if not getattr(sys, 'frozen', False):
            return 0
        bundle_path = sys._MEIPASS
    root = Path(base_path) if base_path is not None else Path(sys.executable).parent
    bundle = Path(bundle_path)
    copied = 0
    sources = [(path, valid_metadata) for path in (bundle / 'core').glob('*.json')]
    for folder in ('agents', 'ranks', 'maps'):
        sources.extend((path, valid_image) for path in (bundle / 'assets' / folder).glob('*.png'))
    for source, validator in sources:
        target = root / source.relative_to(bundle)
        if validator(target):
            continue
        if not validator(source):
            raise RuntimeError(f'Bundled resource is invalid: {source.name}')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    return copied
