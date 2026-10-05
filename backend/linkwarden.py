"""Linkwarden API integration with a separate, verified token for each ControlDeck user."""
import hashlib
import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import requests
from flask import g, jsonify, request
from backend.auth import filter_configuration
from backend.configuration import load_config


class LinkwardenError(Exception):
    pass


def base_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Ongeldig Linkwarden-adres.')
    parts = urlsplit(value)
    try:
        _ = parts.port
        local = ipaddress.ip_address(parts.hostname or '').is_private
    except ValueError:
        local = False
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('', '/', '/dashboard') or parts.scheme not in ('http', 'https') or (parts.scheme == 'http' and not local):
        raise ValueError('Gebruik HTTPS, of een intern IP-adres met HTTP, zonder extra pad.')
    try:
        _ = parts.port
    except ValueError:
        raise ValueError('Ongeldige poort.') from None
    return f'{parts.scheme}://{parts.netloc}'.rstrip('/')


def save_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(value, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def upstream(url, token, endpoint, *, method='GET', params=None, body=None):
    try:
        response = requests.request(method, url + '/api/v1' + endpoint,
            headers={'Authorization': 'Bearer ' + token}, params=params, json=body,
            timeout=10, allow_redirects=False)
        if response.status_code in (401, 403):
            raise LinkwardenError('Linkwarden weigert de toegang. Controleer je persoonlijke API-token.')
        if response.status_code not in (200, 201):
            raise LinkwardenError('Linkwarden kon de aanvraag niet uitvoeren.')
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError('Invalid response')
        return value
    except (requests.RequestException, ValueError):
        raise LinkwardenError('Linkwarden is niet bereikbaar of geeft een ongeldig antwoord.') from None


def verify_identity(url, token, email, linked_id=None):
    if not isinstance(token, str) or not 20 <= len(token) <= 4096 or not re.fullmatch(r'[A-Za-z0-9._~-]+', token):
        raise ValueError('Ongeldige API-token.')
    profile = upstream(url, token, '/users/me').get('response')
    local_match = isinstance(profile, dict) and not profile.get('email') and type(linked_id) is int and linked_id > 0 and profile.get('id') == linked_id
    if not local_match and (not isinstance(profile, dict) or not isinstance(profile.get('email'), str) or profile['email'].casefold() != email.casefold()):
        raise LinkwardenError('Gebruik een Linkwarden-token van hetzelfde e-mailadres als je ControlDeck-account.')


def link_rows(value):
    data = value.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('links'), list):
        raise LinkwardenError('Linkwarden geeft een ongeldig zoekresultaat.')
    rows = []
    for item in data['links'][:100]:
        if not isinstance(item, dict) or type(item.get('id')) is not int:
            continue
        url = item.get('url')
        if not isinstance(url, str) or len(url) > 4096:
            continue
        try:
            parts = urlsplit(url)
            if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
                continue
        except ValueError:
            continue
        collection = item.get('collection') or {}
        rows.append({'id': item['id'], 'url': url, 'name': str(item.get('name') or url)[:300],
            'description': str(item.get('description') or '')[:1000],
            'collection': str(collection.get('name') or '')[:200] if isinstance(collection, dict) else '',
            'tags': [str(tag['name'])[:100] for tag in item.get('tags', []) if isinstance(tag, dict) and 'name' in tag][:30]})
    cursor = data.get('nextCursor')
    return {'links': rows, 'nextCursor': cursor if type(cursor) is int and cursor > 0 else None}


def setup_linkwarden(app, configuration_path, data_dir):
    root = Path(data_dir) / 'linkwarden'
    connection_path = root / 'connection.json'

    def connection():
        try:
            return base_url(json.loads(connection_path.read_text())['url'])
        except (OSError, ValueError, KeyError, TypeError):
            raise LinkwardenError('Linkwarden is nog niet gekoppeld. Vraag je beheerder om de verbinding in te stellen.') from None

    def token_path(url):
        # Changing the upstream never forwards an old token to the new server.
        name = hashlib.sha256((url + '\n' + g.account['email']).encode()).hexdigest()
        return root / 'users' / (name + '.json')

    def credentials():
        url = connection()
        try:
            stored = json.loads(token_path(url).read_text())
            token = stored['token']
        except (OSError, ValueError, KeyError):
            raise LinkwardenError('Koppel eerst je persoonlijke Linkwarden-API-token.') from None
        verify_identity(url, token, g.account['email'], stored.get('upstreamUserId'))
        return url, token

    @app.before_request
    def linkwarden_access():
        if request.path.startswith('/api/linkwarden') and g.account is not None:
            if not any(module['id'] == 'bookmarks' for module in filter_configuration(load_config(configuration_path), g.account)['modules']):
                return jsonify(error='Geen toegang tot Bookmarks.'), 403
            if request.path.startswith('/api/linkwarden/connection') and g.account['role'] != 'admin':
                return jsonify(error='Beheerrechten vereist.'), 403

    @app.errorhandler(LinkwardenError)
    def linkwarden_error(error):
        return jsonify(error=str(error)), 502

    @app.route('/api/linkwarden/connection', methods=['GET', 'PUT', 'DELETE'])
    def manage_connection():
        if request.method == 'DELETE':
            connection_path.unlink(missing_ok=True)
            return jsonify(connected=False)
        if request.method == 'PUT':
            value = request.get_json(silent=True)
            try:
                if not isinstance(value, dict) or set(value) != {'url'}:
                    raise ValueError('Ongeldige verbinding.')
                url = base_url(value['url'])
            except ValueError as error:
                return jsonify(error=str(error)), 400
            save_private(connection_path, {'url': url})
        try:
            return jsonify(connected=True, url=connection())
        except LinkwardenError:
            return jsonify(connected=False)

    @app.route('/api/linkwarden/token', methods=['GET', 'PUT', 'DELETE'])
    def personal_token():
        url = connection()
        path = token_path(url)
        if request.method == 'DELETE':
            path.unlink(missing_ok=True)
        elif request.method == 'PUT':
            value = request.get_json(silent=True)
            try:
                if not isinstance(value, dict) or set(value) != {'token'}:
                    raise ValueError('Ongeldige tokengegevens.')
                verify_identity(url, value['token'], g.account['email'])
            except ValueError as error:
                return jsonify(error=str(error)), 400
            save_private(path, {'token': value['token']})
        return jsonify(connected=path.is_file(), url=url)

    @app.get('/api/linkwarden/bookmarks')
    def bookmarks():
        query = request.args.get('query', '')
        cursor = request.args.get('cursor')
        collection = request.args.get('collection')
        if len(query) > 200 or any(value is not None and not re.fullmatch(r'[1-9][0-9]{0,9}', value) for value in (cursor, collection)):
            return jsonify(error='Ongeldig zoekfilter.'), 400
        url, token = credentials()
        params = {'sort': 0, 'searchQueryString': query}
        if cursor: params['cursor'] = cursor
        if collection: params['collectionId'] = collection
        return jsonify(link_rows(upstream(url, token, '/search', params=params)))

    @app.get('/api/linkwarden/collections')
    def collections():
        url, token = credentials()
        value = upstream(url, token, '/collections').get('response')
        if not isinstance(value, list):
            raise LinkwardenError('Linkwarden geeft ongeldige collecties.')
        return jsonify(collections=[{'id': item['id'], 'name': str(item.get('name', ''))[:200]}
            for item in value[:1000] if isinstance(item, dict) and type(item.get('id')) is int])

    @app.post('/api/linkwarden/bookmarks')
    def create_bookmark():
        value = request.get_json(silent=True)
        if not isinstance(value, dict) or set(value) != {'url', 'name', 'collectionId'} or not isinstance(value['url'], str) or len(value['url']) > 2048 or not isinstance(value['name'], str) or len(value['name']) > 300 or type(value['collectionId']) is not int or value['collectionId'] <= 0:
            return jsonify(error='Vul een geldig adres, titel en collectie in.'), 400
        try:
            parts = urlsplit(value['url'])
            if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or any(c.isspace() or ord(c) < 32 for c in value['url']):
                raise ValueError('URL')
        except ValueError:
            return jsonify(error='Gebruik een geldig HTTP- of HTTPS-adres.'), 400
        url, token = credentials()
        upstream(url, token, '/links', method='POST', body={'url': value['url'], 'name': value['name'], 'collection': {'id': value['collectionId']}})
        return jsonify(saved=True), 201
