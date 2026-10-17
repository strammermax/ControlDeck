"""Files: a narrow WebDAV proxy to each user's own Nextcloud files. App passwords never reach the browser."""

import hashlib
import json
import re
import secrets
import time
import xml.etree.ElementTree as ElementTree
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import requests
from flask import Response, g, jsonify, request, session, stream_with_context

from backend.auth import filter_configuration, is_manager
from backend.configuration import load_config
from backend.linkwarden import save_private

CHUNK_SIZE = 32 * 1024 * 1024          # below nginx client_max_body_size (50m) and Cloudflare's 100 MB
MAX_UPLOAD = 10 * 1024 ** 3            # 10 GB per file
MAX_PATH = 1024
PENDING_SECONDS = 20 * 60
TIMEOUT = (10, 120)
DAV = '{DAV:}'
PROPFIND = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/><d:getcontentlength/>'
            '<d:getlastmodified/><d:getcontenttype/></d:prop></d:propfind>')


class SizedStream:
    """A request body with a known length, so requests sends it with Content-Length instead of chunked."""

    def __init__(self, stream, length):
        self.stream, self.length = stream, length

    def __len__(self):
        return self.length

    def read(self, size=-1):
        return self.stream.read(size)


class FilesError(Exception):
    # Not 502: Cloudflare replaces origin 502 responses with its own page, hiding this message.
    status = 424


class RelinkError(FilesError):
    status = 409


class ConflictError(FilesError):
    status = 409


def nextcloud_origin(value):
    """HTTPS origin without path, or plain HTTP only for a private IP inside the homelab."""
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Ongeldig Nextcloud-adres.')
    parts = urlsplit(value.rstrip('/'))
    try:
        _ = parts.port
    except ValueError:
        raise ValueError('Ongeldige poort.') from None
    private = bool(re.fullmatch(r'(10|127)(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2}', parts.hostname or ''))
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password or parts.query \
            or parts.fragment or parts.path not in ('',) or (parts.scheme == 'http' and not private):
        raise ValueError('Gebruik het HTTPS-adres van Nextcloud zonder pad, bijvoorbeeld https://cloud.example.org.')
    return f'{parts.scheme}://{parts.netloc}'


def clean_path(value, allow_root=True):
    """Relative path inside the user's own files as a list of segments; refuses traversal and control characters."""
    if value is None:
        value = ''
    if not isinstance(value, str) or len(value) > MAX_PATH or any(ord(c) < 32 or c == '\x7f' for c in value) or '\\' in value:
        raise ValueError('Ongeldig pad.')
    segments = [part for part in value.split('/') if part]
    if any(part in ('.', '..') or len(part) > 255 for part in segments):
        raise ValueError('Ongeldig pad.')
    if not segments and not allow_root:
        raise ValueError('Kies een bestand of map, niet de hoofdmap.')
    return segments


def join_path(segments):
    return '/'.join(segments)


def dav_items(xml_text, base_path):
    """Project a PROPFIND multistatus to name/type/size/modified, skipping the folder itself."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        raise FilesError('Nextcloud geeft een ongeldig mapoverzicht.') from None
    items = []
    for response in root.findall(DAV + 'response'):
        href = unquote(response.findtext(DAV + 'href') or '')
        if not href.startswith(base_path):
            continue
        relative = href[len(base_path):].strip('/')
        if not relative or '/' in relative:
            continue
        prop = next((p.find(DAV + 'prop') for p in response.findall(DAV + 'propstat') if '200' in (p.findtext(DAV + 'status') or '')), None)
        if prop is None:
            continue
        folder = prop.find(DAV + 'resourcetype') is not None and prop.find(DAV + 'resourcetype').find(DAV + 'collection') is not None
        size = prop.findtext(DAV + 'getcontentlength')
        modified = prop.findtext(DAV + 'getlastmodified')
        try:
            stamp = int(parsedate_to_datetime(modified).timestamp()) if modified else None
        except (TypeError, ValueError):
            stamp = None
        items.append({'name': relative[:255], 'type': 'folder' if folder else 'file',
                      'size': int(size) if size and size.isdigit() and not folder else None, 'modified': stamp})
    return sorted(items, key=lambda item: (item['type'] != 'folder', item['name'].casefold()))


def setup_files(app, configuration_path, data_dir):
    root = Path(data_dir) / 'files'
    server_path = root / 'server.json'

    def origin():
        try:
            return nextcloud_origin(json.loads(server_path.read_text())['url'])
        except (OSError, ValueError, KeyError, TypeError):
            raise FilesError('Files is nog niet ingericht. Vraag je beheerder het Nextcloud-adres in te stellen.') from None

    def private_path(kind, server):
        # Bound to the stable login subject and server: a new server never receives an old password.
        name = hashlib.sha256((server + '\n' + g.identity_subject).encode()).hexdigest()
        return root / kind / (name + '.json')

    def credentials():
        server = origin()
        try:
            stored = json.loads(private_path('users', server).read_text())
            return server, stored['loginName'], stored['appPassword']
        except (OSError, ValueError, KeyError):
            raise RelinkError('Koppel eerst je Nextcloud-account bij Files.') from None

    def call(method, url, auth=None, **kwargs):
        try:
            return requests.request(method, url, auth=auth, timeout=TIMEOUT, allow_redirects=False,
                                    headers={'OCS-APIRequest': 'true', 'User-Agent': 'ControlDeck Files', **kwargs.pop('headers', {})}, **kwargs)
        except requests.RequestException:
            raise FilesError('Nextcloud is niet bereikbaar.') from None

    def dav(method, segments, *, headers=None, base='files', **kwargs):
        server, login, password = credentials()
        url = f'{server}/remote.php/dav/{base}/{quote(login, safe="")}/' + '/'.join(quote(part, safe='') for part in segments)
        response = call(method, url, auth=(login, password), headers=headers or {}, **kwargs)
        if response.status_code == 401:
            response.close()
            raise RelinkError('Je Nextcloud-koppeling is verlopen of ingetrokken. Koppel opnieuw.')
        return response, server, login

    def destination(segments):
        server, login, _ = credentials()
        return f'{server}/remote.php/dav/files/{quote(login, safe="")}/' + '/'.join(quote(part, safe='') for part in segments)

    def verify_identity(server, login, password):
        response = call('GET', server + '/ocs/v2.php/cloud/user?format=json', auth=(login, password))
        try:
            data = response.json()['ocs']['data'] if response.status_code == 200 else None
        except (ValueError, KeyError, TypeError):
            data = None
        email = data.get('email') if isinstance(data, dict) else None
        if not isinstance(email, str) or email.casefold() != g.account['email'].casefold():
            revoke(server, login, password)
            raise FilesError('Gebruik het Nextcloud-account met hetzelfde e-mailadres als je ControlDeck-account.')

    def revoke(server, login, password):
        try:
            call('DELETE', server + '/ocs/v2.php/core/apppassword', auth=(login, password))
        except FilesError:
            pass

    def expect(response, ok, message):
        if response.status_code not in ok:
            response.close()
            # Status and method only: never URLs with personal paths, headers or credentials.
            app.logger.warning('Files upstream %s gaf status %s', response.request.method if getattr(response, 'request', None) else '?', response.status_code)
            if response.status_code in (404,):
                raise FilesError('Bestand of map niet gevonden.')
            if response.status_code in (405, 412):
                raise ConflictError('Er bestaat al een bestand of map met die naam.')
            if response.status_code == 507:
                raise FilesError('Onvoldoende opslagruimte in Nextcloud.')
            raise FilesError(f'{message} (Nextcloud-status {response.status_code})')
        return response

    def body_path(name='path', allow_root=False):
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError('Ongeldige aanvraag.')
        return value, clean_path(value.get(name), allow_root)

    @app.before_request
    def files_access():
        if request.path.startswith('/api/files') and g.account is not None:
            if not any(module['id'] == 'files' for module in filter_configuration(load_config(configuration_path), g.account)['modules']):
                return jsonify(error='Geen toegang tot Files.'), 403
            if request.path == '/api/files/server' and request.method != 'GET' and not is_manager(g.account):
                return jsonify(error='Beheerrechten vereist.'), 403
            g.identity_subject = session['identity']['sub']

    @app.errorhandler(FilesError)
    def files_error(error):
        return jsonify(error=str(error), relink=isinstance(error, RelinkError)), error.status

    @app.route('/api/files/server', methods=['GET', 'PUT', 'DELETE'])
    def files_server():
        if request.method == 'DELETE':
            server_path.unlink(missing_ok=True)
        elif request.method == 'PUT':
            value = request.get_json(silent=True)
            try:
                if not isinstance(value, dict) or set(value) != {'url'}:
                    raise ValueError('Ongeldige instelling.')
                save_private(server_path, {'url': nextcloud_origin(value['url'])})
            except ValueError as error:
                return jsonify(error=str(error)), 400
        try:
            return jsonify(configured=True, url=origin())
        except FilesError:
            return jsonify(configured=False, url=None)

    @app.route('/api/files/connection', methods=['GET', 'POST', 'DELETE'])
    def files_connection():
        server = origin()
        path = private_path('users', server)
        if request.method == 'DELETE':
            try:
                stored = json.loads(path.read_text())
                revoke(server, stored['loginName'], stored['appPassword'])
            except (OSError, ValueError, KeyError):
                pass
            path.unlink(missing_ok=True)
            private_path('pending', server).unlink(missing_ok=True)
        elif request.method == 'POST':
            # Login Flow v2: Nextcloud returns a login page for the browser and a poll token for this server only.
            response = call('POST', server + '/index.php/login/v2')
            try:
                value = response.json() if response.status_code == 200 else {}
                login_url, poll = value['login'], value['poll']
                token, endpoint = poll['token'], poll['endpoint']
                if not (isinstance(login_url, str) and login_url.startswith(server + '/') and isinstance(endpoint, str)
                        and endpoint.startswith(server + '/') and isinstance(token, str) and 20 <= len(token) <= 512):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                raise FilesError('Nextcloud kon de koppeling niet starten.') from None
            save_private(private_path('pending', server), {'token': token, 'endpoint': endpoint, 'created': int(time.time())})
            return jsonify(loginUrl=login_url)
        try:
            login = json.loads(path.read_text())['loginName']
        except (OSError, ValueError, KeyError):
            login = None
        return jsonify(linked=login is not None, loginName=login, server=server)

    @app.post('/api/files/connection/poll')
    def files_connection_poll():
        server = origin()
        pending_path = private_path('pending', server)
        try:
            pending = json.loads(pending_path.read_text())
        except (OSError, ValueError):
            return jsonify(error='Er loopt geen koppeling. Start opnieuw.'), 409
        if time.time() - pending.get('created', 0) > PENDING_SECONDS:
            pending_path.unlink(missing_ok=True)
            return jsonify(error='De koppeling is verlopen. Start opnieuw.'), 409
        response = call('POST', pending['endpoint'], data={'token': pending['token']})
        if response.status_code == 404:
            return jsonify(state='pending')
        try:
            value = response.json() if response.status_code == 200 else {}
            login, password = value['loginName'], value['appPassword']
            if nextcloud_origin(value['server']) != server or not isinstance(login, str) or not isinstance(password, str) \
                    or not 1 <= len(login) <= 255 or not 20 <= len(password) <= 512:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            pending_path.unlink(missing_ok=True)
            raise FilesError('Nextcloud gaf een ongeldig koppelresultaat.') from None
        pending_path.unlink(missing_ok=True)
        verify_identity(server, login, password)
        save_private(private_path('users', server), {'loginName': login, 'appPassword': password})
        return jsonify(state='linked', loginName=login)

    @app.get('/api/files/list')
    def files_list():
        try:
            segments = clean_path(request.args.get('path'))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, login = dav('PROPFIND', segments, headers={'Depth': '1', 'Content-Type': 'application/xml'}, data=PROPFIND)
        expect(response, (207,), 'Map kon niet worden gelezen.')
        base = f'/remote.php/dav/files/{login}/' + join_path(segments)
        return jsonify(path=join_path(segments), items=dav_items(response.content, base.rstrip('/') + '/'))

    @app.get('/api/files/download')
    def files_download():
        try:
            segments = clean_path(request.args.get('path'), allow_root=False)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('GET', segments, stream=True)
        expect(response, (200,), 'Bestand kon niet worden gedownload.')
        headers = {
            # Never render uploaded content on the ControlDeck origin.
            'Content-Disposition': "attachment; filename*=UTF-8''" + quote(segments[-1], safe=''),
            'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; sandbox", 'Cache-Control': 'no-store',
        }
        if (response.headers.get('Content-Length') or '').isdigit():
            headers['Content-Length'] = response.headers['Content-Length']

        def body():
            try:
                yield from response.iter_content(1024 * 1024)
            finally:
                response.close()
        return Response(stream_with_context(body()), mimetype='application/octet-stream', headers=headers)

    def upload_body():
        length = request.content_length
        if length is None or length < 0 or length > CHUNK_SIZE:
            raise ValueError(f'Stuur hooguit {CHUNK_SIZE // (1024 * 1024)} MB per verzoek.')
        request.max_content_length = CHUNK_SIZE
        return SizedStream(request.stream, length), length

    @app.put('/api/files/upload')
    def files_upload():
        try:
            segments = clean_path(request.args.get('path'), allow_root=False)
            stream, length = upload_body()
        except ValueError as error:
            return jsonify(error=str(error)), 400
        overwrite = request.args.get('overwrite') == '1'
        response, _, _ = dav('PUT', segments, data=stream, headers={} if overwrite else {'If-None-Match': '*'})
        expect(response, (201, 204), 'Uploaden mislukt.')
        return jsonify(ok=True), 201

    @app.post('/api/files/uploads')
    def files_upload_start():
        try:
            value, segments = body_path()
            size = value.get('size')
            if type(size) is not int or not 0 < size <= MAX_UPLOAD:
                raise ValueError('Een bestand mag hooguit 10 GB zijn.')
        except ValueError as error:
            return jsonify(error=str(error)), 400
        upload = 'controldeck-' + secrets.token_hex(16)
        response, _, _ = dav('MKCOL', [upload], base='uploads', headers={'Destination': destination(segments)})
        expect(response, (201,), 'Uploaden kon niet starten.')
        return jsonify(id=upload, chunkSize=CHUNK_SIZE), 201

    def upload_id(value):
        if not isinstance(value, str) or not re.fullmatch(r'controldeck-[0-9a-f]{32}', value):
            raise ValueError('Ongeldige upload.')
        return value

    @app.put('/api/files/uploads/<upload>/<int:index>')
    def files_upload_chunk(upload, index):
        try:
            upload = upload_id(upload)
            segments = clean_path(request.args.get('path'), allow_root=False)
            if not 1 <= index <= 10000:
                raise ValueError('Ongeldig deel.')
            stream, length = upload_body()
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('PUT', [upload, f'{index:05d}'], base='uploads', data=stream,
                             headers={'Destination': destination(segments)})
        expect(response, (201, 204), 'Uploaden van een deel mislukt.')
        return jsonify(ok=True), 201

    @app.post('/api/files/uploads/<upload>/finish')
    def files_upload_finish(upload):
        try:
            upload = upload_id(upload)
            value, segments = body_path()
            size = value.get('size')
            if type(size) is not int or not 0 < size <= MAX_UPLOAD:
                raise ValueError('Ongeldige bestandsgrootte.')
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('MOVE', [upload, '.file'], base='uploads', headers={
            'Destination': destination(segments), 'OC-Total-Length': str(size), 'Overwrite': 'T' if value.get('overwrite') is True else 'F'})
        expect(response, (201, 204), 'Samenvoegen van de upload mislukt.')
        return jsonify(ok=True), 201

    @app.delete('/api/files/uploads/<upload>')
    def files_upload_abort(upload):
        try:
            upload = upload_id(upload)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('DELETE', [upload], base='uploads')
        response.close()
        return jsonify(ok=True)

    @app.post('/api/files/folder')
    def files_folder():
        try:
            _, segments = body_path()
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('MKCOL', segments)
        expect(response, (201,), 'Map maken mislukt.')
        return jsonify(ok=True), 201

    @app.post('/api/files/move')
    def files_move():
        try:
            value, source = body_path('from')
            target = clean_path(value.get('to'), allow_root=False)
            if target[:len(source)] == source:
                raise ValueError('Een map kan niet in zichzelf worden geplaatst.')
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('MOVE', source, headers={'Destination': destination(target), 'Overwrite': 'T' if value.get('overwrite') is True else 'F'})
        expect(response, (201, 204), 'Verplaatsen mislukt.')
        return jsonify(ok=True)

    @app.delete('/api/files/item')
    def files_delete():
        try:
            segments = clean_path(request.args.get('path'), allow_root=False)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        response, _, _ = dav('DELETE', segments)
        expect(response, (204,), 'Verwijderen mislukt.')
        return jsonify(ok=True)
