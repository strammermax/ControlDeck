from pathlib import Path
import json,struct
from backend.app import create_app

PUBLIC = Path(__file__).resolve().parents[1] / 'frontend/public'

def test_favicon_normal_available_without_login(tmp_path):
    client = create_app(PUBLIC, data_dir=tmp_path).test_client()
    for name in ('favicon.ico','favicon-32x32.png','apple-touch-icon.png','site.webmanifest'):
        response = client.get('/'+name)
        assert response.status_code == 200
        assert response.data == (PUBLIC/name).read_bytes()
    manifest = json.loads(client.get('/site.webmanifest').data)
    assert manifest['short_name'] == 'ControlDeck'
    for icon in manifest['icons']:
        assert client.get(icon['src']).status_code == 200

def test_favicon_boundary_smallest_and_largest_sizes(tmp_path):
    client = create_app(PUBLIC, data_dir=tmp_path).test_client()
    for name,size in (('favicon-16x16.png',16),('android-chrome-512x512.png',512)):
        data=client.get('/'+name).data
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II',data[16:24]) == (size,size)

def test_favicon_failure_missing_and_parent_path(tmp_path):
    client = create_app(PUBLIC, data_dir=tmp_path).test_client()
    for path in ('/missing-favicon.png','/%2e%2e/app/layout.tsx','/%2e%2e/%2e%2e/secrets/token-linkwarden.txt'):
        assert client.get(path).status_code == 404
