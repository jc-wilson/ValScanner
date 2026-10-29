import asyncio
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import requests

from core.resource_cache import download_image, seed_runtime_resources, valid_image


ROOT = Path(__file__).resolve().parent


def png_bytes():
    data = BytesIO()
    Image.new('RGBA', (8, 8), '#3a86ff').save(data, 'PNG')
    return data.getvalue()


class AssetCacheTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'build').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, (ROOT / 'build').resolve())
        self.addCleanup(self.temp.cleanup)

    def test_http_errors_and_html_never_replace_a_valid_image(self):
        target = self.root / 'image.png'
        target.write_bytes(png_bytes())
        before = target.read_bytes()
        error = Mock(content=b'not found')
        error.raise_for_status.side_effect = requests.HTTPError('404')
        html = Mock(content=b'<html>temporarily unavailable</html>')
        for response in (error, html):
            with patch('core.resource_cache.requests.get', return_value=response):
                self.assertFalse(download_image('https://example.test/image', target))
            self.assertEqual(target.read_bytes(), before)
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_download_creates_parent_directories_and_valid_image(self):
        target = self.root / 'new-cache' / 'skin.png'
        response = Mock(content=png_bytes())
        with patch('core.resource_cache.requests.get', return_value=response):
            self.assertTrue(download_image('https://example.test/image', target))
        self.assertTrue(valid_image(target))

    def test_seeding_repairs_invalid_files_and_preserves_newer_cache_and_settings(self):
        bundle, installed = self.root / 'bundle', self.root / 'installed'
        (bundle / 'core').mkdir(parents=True)
        (bundle / 'assets' / 'maps').mkdir(parents=True)
        metadata = bundle / 'core' / 'map_uuids.json'
        metadata.write_text(json.dumps({'data': [{'uuid': 'old'}]}))
        (bundle / 'assets' / 'maps' / 'map.png').write_bytes(png_bytes())
        settings = installed / 'agent_selection' / 'app_state.json'
        settings.parent.mkdir(parents=True)
        settings.write_text('{"selected_theme":"rosewood"}')
        self.assertEqual(seed_runtime_resources(installed, bundle), 2)
        cached = installed / 'core' / 'map_uuids.json'
        cached.write_text(json.dumps({'data': [{'uuid': 'new'}]}))
        cached_image = installed / 'assets' / 'maps' / 'map.png'
        cached_image.write_bytes(b'broken download')
        self.assertEqual(seed_runtime_resources(installed, bundle), 1)
        self.assertEqual(json.loads(cached.read_text())['data'][0]['uuid'], 'new')
        self.assertTrue(valid_image(cached_image))
        self.assertEqual(settings.read_text(), '{"selected_theme":"rosewood"}')
        self.assertEqual(seed_runtime_resources(installed, bundle), 0)

    def test_corrupt_cosmetic_cache_is_downloaded_again(self):
        from core.asset_loader import _ensure_asset_files
        target = self.root / 'skin.png'
        target.write_bytes(b'previous bad download')
        response = Mock(content=png_bytes())
        with patch('core.resource_cache.requests.get', return_value=response) as request:
            asyncio.run(_ensure_asset_files(
                ['skin'], lambda: {'skin': 'https://example.test/skin'}, lambda _: str(target), 'skin'))
        request.assert_called_once()
        self.assertTrue(valid_image(target))


if __name__ == '__main__':
    unittest.main()
