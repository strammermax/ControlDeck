"""Personal bookmark launches: only native SSO routes and Kasm login tickets.

Secrets live in Infisical. SQLite only binds an owner's vault record to the
exact bookmark URL, so changing a shared bookmark cannot redirect credentials.
"""
import hashlib
import json
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

import requests
from flask import g, jsonify, request

from backend.auth import database, filter_configuration
from backend.configuration import load_config
from backend.homepage import read_homepage_links, validate_homepage_link
from backend.modules.kasm import kasm_config, launch_login
from backend.modules.launch_urls import secure_origin
from backend.vault import VaultError


def login_settings(value, bookmark_url):
    """Reject unsupported password/API-to-browser conversions and foreign targets."""
    if not isinstance(value, dict):
        raise ValueError('Ongeldige aanmeldinstelling.')
    parsed = urlsplit(bookmark_url)
    origin = secure_origin(f'{parsed.scheme}://{parsed.netloc}')
    method = value.get('method')
    if method == 'sso' and set(value) == {'method', 'loginUrl'}:
        target = validate_homepage_link({'name': 'Login', 'collection': 'Login', 'url': value['loginUrl']})['url']
        url = urlsplit(target)
        if (url.scheme, url.netloc) != (parsed.scheme, parsed.netloc) or url.fragment:
            raise ValueError('De SSO-aanmeldroute moet bij hetzelfde HTTPS-adres horen.')
        if any(key not in {'realm', 'provider'} for key, _ in parse_qsl(url.query)):
            raise ValueError('Gebruik een vaste SSO-route zonder tijdelijke tokens of accountgegevens.')
        if any(ord(c) < 32 or c == '\\' for c in unquote(target)):
            raise ValueError('Ongeldige SSO-route.')
        return {'method': method, 'loginUrl': target}
    if method == 'kasm' and {'method', 'apiKey', 'apiSecret', 'userId'} <= set(value) <= {'method', 'apiKey', 'apiSecret', 'userId', 'apiUrl', 'apiFingerprint'}:
        for key in ('apiKey', 'apiSecret'):
            if not isinstance(value[key], str) or not 1 <= len(value[key]) <= 4096 or any(ord(c) < 32 for c in value[key]):
                raise ValueError('Vul geldige Kasm API-gegevens in.')
        if not isinstance(value['userId'], str):
            raise ValueError('Vul een geldige Kasm-gebruiker-ID in.')
        try:
            user_id = str(uuid.UUID(value['userId']))
        except ValueError:
            raise ValueError('Vul een geldige Kasm-gebruiker-ID in.') from None
        config = {'url': origin, 'apiKey': value['apiKey'], 'apiSecret': value['apiSecret'],
                  'users': {g.account['email']: user_id}}
        # Internal API overrides are deliberately not accepted from ordinary users.
        if value.get('apiUrl') or value.get('apiFingerprint'):
            if g.account['role'] != 'admin':
                raise PermissionError('Alleen een beheerder kan een intern API-adres of certificaat instellen.')
            config.update({key: value[key] for key in ('apiUrl', 'apiFingerprint') if value.get(key)})
        kasm_config(config)
        return {'method': method, 'config': config}
    raise ValueError('Kies een ondersteunde SSO-route of Kasm API-aanmelding. Een losse API-sleutel is geen web-login.')


def setup_bookmark_logins(app, configuration_path, data_dir):
    db_path = Path(data_dir) / 'users.sqlite3'
    links_path = Path(data_dir) / 'homepage/links.json'
    with database(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS bookmark_logins (owner TEXT NOT NULL, link_id INTEGER NOT NULL, url TEXT NOT NULL, method TEXT NOT NULL, PRIMARY KEY(owner,link_id))')

    def vault_key(link_id):
        digest = hashlib.sha256(f"{g.account['email']}\n{link_id}".encode()).hexdigest().upper()
        return 'CONTROLDECK_BOOKMARK_LOGIN_' + digest

    def current_link(link_id):
        return next((row for row in read_homepage_links(links_path) if row['id'] == link_id), None)

    @app.before_request
    def bookmark_login_access():
        if request.path.startswith('/api/bookmark-logins') and g.account is not None:
            modules = filter_configuration(load_config(configuration_path), g.account)['modules']
            if not any(module['id'] == 'bookmarks' for module in modules):
                return jsonify(error='Geen toegang tot Bookmarks.'), 403

    @app.get('/api/bookmark-logins')
    def bookmark_login_list():
        try:
            links = {row['id']: row['url'] for row in read_homepage_links(links_path)}
            with database(db_path) as db:
                rows = db.execute('SELECT link_id,url,method FROM bookmark_logins WHERE owner=?', (g.account['email'],)).fetchall()
            return jsonify(available=app.extensions.get('controldeck_vault') is not None,
                           logins=[{'linkId': row[0], 'method': row[2]} for row in rows if links.get(row[0]) == row[1]])
        except (OSError, ValueError):
            return jsonify(error='Aanmeldinstellingen konden niet worden geladen.'), 503

    @app.route('/api/bookmark-logins/<int:link_id>', methods=['PUT', 'DELETE'])
    @app.post('/api/bookmark-logins/<int:link_id>/launch')
    def bookmark_login_manage(link_id):
        try:
            link = current_link(link_id)
            if link is None:
                return jsonify(error='Bookmark niet gevonden.'), 404
            vault = app.extensions.get('controldeck_vault')
            if vault is None:
                return jsonify(error='Koppel eerst Keyvault om aanmeldgegevens veilig te bewaren.'), 503
            owner, key = g.account['email'], vault_key(link_id)
            if request.method == 'DELETE':
                # Clear the private value as well as the local reference.
                vault.write(key, '')
                with database(db_path) as db:
                    db.execute('DELETE FROM bookmark_logins WHERE owner=? AND link_id=?', (owner, link_id))
                return jsonify(saved=False)
            if request.method == 'PUT':
                value = login_settings(request.get_json(silent=True), link['url'])
                vault.write(key, json.dumps({'url': link['url'], 'settings': value}))
                with database(db_path) as db:
                    db.execute('INSERT INTO bookmark_logins(owner,link_id,url,method) VALUES(?,?,?,?) ON CONFLICT(owner,link_id) DO UPDATE SET url=excluded.url,method=excluded.method',
                               (owner, link_id, link['url'], value['method']))
                return jsonify(saved=True, method=value['method'])
            if request.get_json(silent=True) != {}:
                return jsonify(error='Deze aanmelding accepteert geen doeladres of account uit de browser.'), 400
            with database(db_path) as db:
                row = db.execute('SELECT url,method FROM bookmark_logins WHERE owner=? AND link_id=?', (owner, link_id)).fetchone()
            if row is None or row[0] != link['url']:
                return jsonify(error='Stel de aanmelding voor deze bookmark opnieuw in.'), 409
            stored = json.loads(vault.read().get(key, 'null'))
            if not isinstance(stored, dict) or stored.get('url') != link['url']:
                raise VaultError('Aanmeldinstelling ontbreekt.')
            settings = stored['settings']
            if settings.get('method') == 'sso' and row[1] == 'sso':
                target = login_settings(settings, link['url'])['loginUrl']
            elif settings.get('method') == 'kasm' and row[1] == 'kasm':
                # Never use a caller-supplied user: the saved map is bound to this owner.
                target = launch_login(settings['config'], g.account)
            else:
                raise ValueError('Ongeldige aanmeldmethode.')
            response = jsonify(url=target)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
            return response
        except PermissionError:
            return jsonify(error='Geen rechten voor deze aanmeldinstelling.'), 403
        except VaultError:
            return jsonify(error='Keyvault is niet beschikbaar of de aanmeldgegevens ontbreken.'), 503
        except (requests.RequestException, OSError, KeyError, TypeError):
            return jsonify(error='Automatisch aanmelden is niet beschikbaar. Controleer de koppeling.'), 503
        except ValueError:
            # Never reflect upstream messages or submitted credential fields.
            return jsonify(error='Ongeldige of niet-ondersteunde aanmeldinstelling. Gebruik HTTPS, een vaste SSO-route of geldige Kasm API-gegevens.'), 400
