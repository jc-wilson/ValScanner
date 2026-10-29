"""Create a Windows executable with a fresh, consistent application identity."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import string
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def prepare_build():
    alphabet = ''.join(c for c in string.ascii_lowercase if c not in 'vs')
    name = ''.join(secrets.choice(alphabet) for _ in range(16))
    stage = ROOT / 'build' / name
    stage.mkdir(parents=True, exist_ok=False)
    for folder in ('core', 'frontend'):
        target = stage / folder
        target.mkdir()
        for source in (ROOT / folder).iterdir():
            if source.suffix in ('.py', '.json') and source.name != '_build_identity.py':
                shutil.copy2(source, target / source.name)

    (stage / 'core' / '_build_identity.py').write_text(
        f'APP_NAME = {name!r}\nCONTACT_ID = {str(uuid.uuid4())!r}\n',
        encoding='utf-8',
    )
    shutil.copy2(ROOT / 'qt_runtime_hook.py', stage / 'qt_runtime_hook.py')

    assets = stage / 'assets'
    assets.mkdir()
    for source in (ROOT / 'assets').iterdir():
        if source.is_file() and not source.name.lower().startswith('logo'):
            shutil.copy2(source, assets / source.name)
    for folder in ('fonts', 'agents', 'ranks'):
        shutil.copytree(ROOT / 'assets' / folder, assets / folder)

    from PIL import Image, ImageDraw

    image = Image.new('RGBA', (256, 256), (19, 24, 36, 255))
    draw = ImageDraw.Draw(image)
    color = tuple(80 + secrets.randbelow(160) for _ in range(3)) + (255,)
    for row in range(5):
        for col in range(3):
            if col == 2 or secrets.randbits(1):
                for mirrored_col in {col, 4 - col}:
                    x, y = 28 + mirrored_col * 40, 28 + row * 40
                    draw.rounded_rectangle((x, y, x + 32, y + 32), radius=6, fill=color)
    image.save(assets / 'app.png')
    image.save(stage / 'app.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])

    source = (stage / 'frontend' / 'QApplication.py').read_text(encoding='utf-8-sig')
    version = re.search(r'^CURRENT_VERSION = "([\d.]+)"', source, re.MULTILINE).group(1)
    version_tuple = tuple(int(part) for part in version.split('.'))
    version_tuple = (version_tuple + (0, 0, 0, 0))[:4]
    fields = {
        'CompanyName': '', 'FileDescription': name, 'FileVersion': version,
        'InternalName': name, 'OriginalFilename': f'{name}.exe',
        'ProductName': name, 'ProductVersion': version,
    }
    strings = ',\n'.join(f'StringStruct({key!r}, {value!r})' for key, value in fields.items())
    (stage / 'version.txt').write_text(
        f'VSVersionInfo(ffi=FixedFileInfo(filevers={version_tuple!r}, '
        f'prodvers={version_tuple!r}, mask=0x3f, flags=0, OS=0x40004, '
        'fileType=1, subtype=0, date=(0, 0)), '
        f'kids=[StringFileInfo([StringTable("040904B0", [{strings}])]), '
        'VarFileInfo([VarStruct("Translation", [1033, 1200])])])',
        encoding='utf-8',
    )
    return name, stage


def prepare_downloads(stage):
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from core.resource_cache import download_image, valid_image, valid_metadata
    from core.valorant_api_cache import VALORANT_API_JSON_MANIFEST

    cache = ROOT / '.build-tools' / 'asset-cache'
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1)))
    for label, relative, url in VALORANT_API_JSON_MANIFEST:
        stored = cache / relative
        destination = stage / relative
        try:
            response = session.get(url, timeout=(5, 30))
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('data'), list) or not payload['data']:
                raise ValueError(f'Invalid metadata: {label}')
            stored.parent.mkdir(parents=True, exist_ok=True)
            stored.write_text(json.dumps(payload), encoding='utf-8')
        except (requests.RequestException, ValueError) as exc:
            if not valid_metadata(stored) and not valid_metadata(destination):
                raise RuntimeError(f'Could not download {label}. Check your internet connection and build again.') from exc
            print(f'Using cached {label} metadata.', flush=True)
        if valid_metadata(stored):
            shutil.copyfile(stored, destination)

    maps = json.loads((stage / 'core' / 'map_uuids.json').read_text(encoding='utf-8'))['data']
    excluded = {
        '1f10dab3-4294-3827-fa35-c2aa00213cf3', '5914d1e0-40c4-cfdd-6b88-eba06347686c',
        'a38a3f9a-4042-844c-8970-a3ac2f7ce93d', 'a264de0f-4a04-9c78-c97a-a6b192ce6e86',
        'a9009649-421f-d5d5-f80c-0cbe02c125bb', 'ee613ee9-28b7-4beb-9666-08db13bb2244',
    }
    map_jobs = [(item['uuid'], item['listViewIconTall']) for item in maps
                if item.get('listViewIconTall') and item.get('uuid') not in excluded]
    def prepare_map(job):
        map_id, url = job
        target = cache / 'assets' / 'maps' / f'{map_id}.png'
        if not valid_image(target) and not download_image(url, target):
            raise RuntimeError(f'Could not download a map image ({map_id}). Check your connection and build again.')
        destination = stage / 'assets' / 'maps' / target.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, destination)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(prepare_map, map_jobs))
    if not map_jobs:
        raise RuntimeError('The map image list is empty. Please try the build again later.')
    for path in (stage / 'assets').rglob('*'):
        if path.suffix.lower() == '.png' and not valid_image(path):
            raise RuntimeError(f'Invalid asset: {path.relative_to(stage)}')
    print(f'Prepared all five metadata files and {len(map_jobs)} map images.', flush=True)


def build(name, stage):
    prepare_downloads(stage)
    env = os.environ.copy()
    windows = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    # Keep unrelated tool installations' Qt/ICU DLLs out of this build.
    env['PATH'] = os.pathsep.join(str(path) for path in (
        Path(sys.executable).parent, Path(sys.base_prefix),
        windows / 'System32', windows, windows / 'System32' / 'Wbem',
    ))
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    command = [
        sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
        '--onefile', '--windowed', '--name', name,
        '--paths', str(stage), '--distpath', str(ROOT / 'dist'),
        '--workpath', str(stage / 'pyinstaller'), '--specpath', str(stage),
        '--runtime-hook', 'qt_runtime_hook.py', '--icon', 'app.ico',
        '--version-file', 'version.txt', '--add-data', 'assets;assets',
        '--add-data', 'core/*.json;core', '--collect-data', 'qtawesome',
        '--hidden-import', 'cryptography.hazmat.primitives.serialization.pkcs12',
        '--hidden-import', 'PySide6.QtNetwork',
    ]
    icu = windows / 'System32' / 'icuuc.dll'
    if icu.exists():
        command += ['--add-binary', f'{icu};.']
    command.append('frontend/QApplication.py')
    subprocess.run(command, cwd=stage, env=env, check=True)
    executable = ROOT / 'dist' / f'{name}.exe'
    subprocess.run([str(executable), '--verify-build'], cwd=ROOT / 'dist',
                   env=env, check=True, timeout=90)
    (ROOT / 'build' / 'last-build.json').write_text(
        json.dumps({'executable': str(executable.resolve()), 'name': name}), encoding='utf-8')
    print(f'Build complete: {executable}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true',
                        help='Generate staged source, identity, icon and metadata without packaging.')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Build the Windows executable on Windows.')
    name, stage = prepare_build()
    print(f'Build name: {name}', flush=True)
    if args.prepare_only:
        print(f'Prepared: {stage}', flush=True)
    else:
        build(name, stage)


if __name__ == '__main__':
    main()
