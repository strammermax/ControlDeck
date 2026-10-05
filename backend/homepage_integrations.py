"""Native Homepage integrations; credentials never leave the encrypted server store."""
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import jsonify, request
from backend.auth import database
from backend.homepage import validate_homepage_link

CATALOG = [
    {'type': 'seerr', 'name': 'Seerr', 'icon': 'jellyseerr', 'authModes': ['apiKey'], 'capabilities': ['request-counts']},
    {'type': 'jellyfin', 'name': 'Jellyfin', 'icon': 'jellyfin', 'authModes': ['apiKey', 'password'], 'capabilities': ['library-counts']},
]


def integration_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Gebruik een HTTP- of HTTPS-adres zonder geheimen.')
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or '\\' in value or '..' in parsed.path.split('/'):
        raise ValueError('Gebruik een HTTP- of HTTPS-adres zonder geheimen.')
    _ = parsed.port
    return value.rstrip('/')


def validate_integration(value):
    if not isinstance(value, dict):
        raise ValueError('Ongeldige integratie.')
    kind = next((item for item in CATALOG if item['type'] == value.get('type')), None)
    if not kind or value.get('authMode') not in kind['authModes']:
        raise ValueError('Deze koppeling wordt niet ondersteund.')
    result = {'type': kind['type'], 'authMode': value['authMode'], 'url': integration_url(value.get('url'))}
    for key, limit in [('name', 300), ('group', 200)]:
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > limit or any(ord(c) < 32 for c in text):
            raise ValueError('Vul een geldige naam en groep in.')
        result[key] = text.strip()
    result['appUrl'] = validate_homepage_link({'name':'App','collection':'Apps','url':value.get('appUrl') or result['url']})['url']
    result['showApp'] = value.get('showApp', True)
    if type(result['showApp']) is not bool:
        raise ValueError('Ongeldige app-instelling.')
    if not urlsplit(result['appUrl']).fragment:
        result['appUrl'] = result['appUrl'].rstrip('/')
    result['linkId'] = value.get('linkId')
    if result['linkId'] is not None and (type(result['linkId']) is not int or result['linkId'] <= 0 or not result['showApp']):
        raise ValueError('Kies een geldige bestaande Homepage-link.')
    credentials = {}
    for key in (['apiKey'] if result['authMode'] == 'apiKey' else ['username', 'password']):
        secret = value.get(key)
        if not isinstance(secret, str) or not secret or len(secret) > 4096 or any(ord(c) < 32 for c in secret):
            raise ValueError('Vul de vereiste toegangsgegevens in.')
        if key == 'apiKey' and not re.fullmatch(r'[A-Za-z0-9._~-]+', secret):
            raise ValueError('Ongeldige API-sleutel.')
        credentials[key] = secret
    return result, credentials


def integration_summary(record, credentials):
    """A fixed read-only endpoint per adapter, with no redirects or raw upstream output."""
    def call(path, headers, body=None):
        response = requests.request('POST' if body is not None else 'GET', record['url'] + path,
                                    headers=headers, json=body, timeout=10, allow_redirects=False)
        if response.status_code in (401, 403):
            raise ValueError('Toegang geweigerd. Controleer de gegevens en rechten.')
        if response.status_code != 200:
            raise ValueError('De toepassing geeft geen geldig antwoord.')
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError('De toepassing geeft geen geldig antwoord.')
        return payload

    try:
        if record['type'] == 'seerr':
            payload = call('/api/v1/request/count', {'X-Api-Key': credentials['apiKey']})
            fields = {'total': 'Aanvragen', 'pending': 'In afwachting', 'available': 'Beschikbaar'}
        else:
            prefix = 'MediaBrowser Client="ControlDeck", Device="ControlDeck", DeviceId="controldeck", Version="1"'
            token = credentials.get('apiKey')
            user_id = None
            if record['authMode'] == 'password':
                auth = call('/Users/AuthenticateByName', {'Authorization': prefix}, {'Username': credentials['username'], 'Pw': credentials['password']})
                token = auth.get('AccessToken')
                user_id = auth.get('User', {}).get('Id') if isinstance(auth.get('User'), dict) else None
                if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{1,4096}', token) or not isinstance(user_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', user_id):
                    raise ValueError('De toepassing geeft geen geldig antwoord.')
            path = '/Items/Counts' + ('?userId=' + user_id if user_id else '')
            payload = call(path, {'Authorization': prefix + ', Token="' + token + '"'})
            fields = {'MovieCount': 'Films', 'SeriesCount': 'Series', 'EpisodeCount': 'Afleveringen'}
        if any(type(payload.get(key)) is not int or not 0 <= payload[key] <= 2**53 - 1 for key in fields):
            raise ValueError('De toepassing geeft ongeldige aantallen terug.')
        return [{'label': label, 'value': payload[key]} for key, label in fields.items()]
    except (requests.RequestException, KeyError, TypeError):
        raise ValueError('Verbinding niet beschikbaar. Controleer adres, certificaat en toegang.') from None


def setup_homepage_integrations(app, data_dir):
    db_path = Path(data_dir) / 'users.sqlite3'
    # Domain-separated key derived from the persistent private Flask secret. Back up both.
    cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(('homepage-integrations-v1:' + str(app.secret_key)).encode()).digest()))
    with database(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS homepage_integrations (id INTEGER PRIMARY KEY AUTOINCREMENT, metadata TEXT NOT NULL, credentials TEXT NOT NULL)')

    @app.get('/api/homepage/integrations/catalog')
    def homepage_integration_catalog():
        return jsonify(integrations=CATALOG)

    @app.route('/api/homepage/integrations', methods=['GET', 'POST'])
    @app.route('/api/homepage/integrations/<int:integration_id>', methods=['PUT', 'DELETE'])
    def homepage_integration_records(integration_id=None):
        try:
            if request.method == 'GET':
                with database(db_path) as db:
                    rows = db.execute('SELECT id, metadata FROM homepage_integrations ORDER BY id').fetchall()
                return jsonify(integrations=[{'id': row[0], **json.loads(row[1])} for row in rows])
            if request.method == 'DELETE':
                with database(db_path) as db:
                    found = db.execute('DELETE FROM homepage_integrations WHERE id=?', (integration_id,)).rowcount
                return (jsonify(deleted=True), 200) if found else (jsonify(error='Integratie niet gevonden.'), 404)
            metadata, credentials = validate_integration(request.get_json(silent=True))
            metadata['summary'] = integration_summary(metadata, credentials)
            encrypted = cipher.encrypt(json.dumps(credentials).encode()).decode()
            with database(db_path) as db:
                db.execute('BEGIN IMMEDIATE')
                if metadata['linkId'] is not None:
                    links_path = Path(data_dir) / 'homepage/links.json'
                    links = json.loads(links_path.read_text(encoding='utf-8')) if links_path.exists() else []
                    link = next((item for item in links if item.get('id') == metadata['linkId']), None)
                    if not link:
                        raise ValueError('De bestaande Homepage-link is niet meer beschikbaar.')
                    for row in db.execute('SELECT id, metadata FROM homepage_integrations'):
                        if row[0] != integration_id and json.loads(row[1]).get('linkId') == metadata['linkId']:
                            raise ValueError('Deze Homepage-link is al aan een integratie gekoppeld.')
                    metadata['appUrl'] = validate_homepage_link({'name':'App','collection':'Apps','url':link['url']})['url']
                if request.method == 'POST':
                    if db.execute('SELECT COUNT(*) FROM homepage_integrations').fetchone()[0] >= 50:
                        return jsonify(error='Maximaal 50 integraties toegestaan.'), 400
                    integration_id = db.execute('INSERT INTO homepage_integrations(metadata, credentials) VALUES (?,?)', (json.dumps(metadata), encrypted)).lastrowid
                else:
                    if not db.execute('UPDATE homepage_integrations SET metadata=?, credentials=? WHERE id=?', (json.dumps(metadata), encrypted, integration_id)).rowcount:
                        return jsonify(error='Integratie niet gevonden.'), 404
            return jsonify(integration={'id': integration_id, **metadata}), 201 if request.method == 'POST' else 200
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.get('/api/homepage/integrations/<int:integration_id>/status')
    def integration_status(integration_id):
        with database(db_path) as db:
            row = db.execute('SELECT metadata, credentials FROM homepage_integrations WHERE id=?', (integration_id,)).fetchone()
        if not row:
            return jsonify(error='Integratie niet gevonden.'), 404
        try:
            return jsonify(summary=integration_summary(json.loads(row[0]), json.loads(cipher.decrypt(row[1].encode()))))
        except InvalidToken:
            return jsonify(error='Toegangsgegevens niet leesbaar. Stel de koppeling opnieuw in.'), 503
        except ValueError as error:
            return jsonify(error=str(error)), 502
