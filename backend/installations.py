"""Admin installation plans and a bounded queue for a separate privileged worker."""
import json
import os
import re
import time
import uuid
from threading import Lock
from pathlib import Path

import requests
from flask import g, jsonify, request
from backend.configuration import ConfigurationError, load_config


def validate_install_request(value):
    if not isinstance(value, dict) or set(value) != {'module', 'method', 'target'}:
        raise ValueError('Kies een module, installatiemethode en bestemming.')
    if value['module'] != 'termix' or value['method'] not in ('docker', 'lxc') or value['target'] not in ('local', 'proxmox'):
        raise ValueError('Onbekende module, methode of bestemming.')
    if value['target'] != ('local' if value['method'] == 'docker' else 'proxmox'):
        raise ValueError('De bestemming past niet bij de installatiemethode.')
    return dict(value)


def setup_installations(app, configuration_path, data_dir):
    root = Path(data_dir) / 'installations'
    queue_lock = Lock()
    catalog_root = Path(__file__).resolve().parent.parent / 'config/catalog'

    def status():
        try:
            heartbeat = json.loads((root/'worker.json').read_text())
            worker = isinstance(heartbeat,dict) and type(heartbeat.get('updatedAt')) in (float, int) and 0 <= time.time()-heartbeat['updatedAt'] < 90
        except (OSError, ValueError, TypeError):
            worker = False
        try:
            config = load_config(configuration_path)
            configured = any(p['id']=='termix' and p['type']=='termix' and p['enabled'] for p in config['providers'])
        except ConfigurationError:
            configured = False
        online = False
        if worker:
            try:
                online = requests.get('http://127.0.0.1:8090/users/registration-allowed', timeout=2).status_code==200
            except requests.RequestException:
                pass
        return {'workerAvailable':bool(worker), 'configured':configured, 'online':online}

    @app.before_request
    def administrative_access():
        if request.path.startswith('/api/installations') and g.account is not None and g.account['role']!='admin':
            return jsonify(error='Beheerrechten vereist om modules te installeren.'),403

    @app.get('/api/installations')
    def catalog():
        try:
            # Installable modules first, then connections; each entry is reviewed metadata only.
            modules = sorted((json.loads(item.read_text()) for item in catalog_root.glob('*.json')), key=lambda module: (module.get('kind', 'install') != 'install', module['id']))
            for module in modules:
                module.setdefault('kind', 'install')
            return jsonify(modules=modules, status=status(), connections={name: (Path(data_dir) / name / 'connection.json').is_file() for name in ('proxmox', 'proxmenux')})
        except (OSError, ValueError):
            return jsonify(error='De modulecatalogus is niet beschikbaar.'),503

    @app.post('/api/installations/plan')
    def plan():
        try:
            selected=validate_install_request(request.get_json(silent=True))
        except ValueError as error:
            return jsonify(error=str(error)),400
        state=status()
        blockers=[]
        if selected['method']=='lxc':
            blockers.append('De Proxmox-verbinding voor het aanmaken van een LXC is nog niet ingericht.')
        elif not state['workerAvailable']:
            blockers.append('De installatieservice is nog niet beschikbaar op deze ControlDeck-host.')
        return jsonify(**selected, canInstall=not blockers, blockers=blockers,
            alreadyInstalled=state['online'] and state['configured'] if selected['method']=='docker' else False,
            resources={'cpu':1,'memoryMb':512,'diskGb':None} if selected['method']=='docker' else {'cpu':4,'memoryMb':4096,'diskGb':10},
            steps=(['Start de vastgepinde Termix-container met blijvende opslag.'] if selected['method']=='docker' else ['Maak een nieuwe LXC aan via Proxmox VE Helper-Scripts.']) + ['Controleer of Termix gereed is.', 'Koppel de ControlDeck-login en rollen.', 'Activeer de Terminal-module.'],
            installer='docker-compose' if selected['method']=='docker' else 'proxmox-helper-scripts',
            documentation='https://docs.termix.site/install/server/docker/' if selected['method']=='docker' else 'https://docs.termix.site/install/server/proxmox/',
            preservesData=True)

    @app.post('/api/installations/jobs')
    def enqueue():
        try:
            selected=validate_install_request(request.get_json(silent=True))
        except ValueError as error:
            return jsonify(error=str(error)),400
        if selected['method']!='docker':
            return jsonify(error='Richt eerst de Proxmox-verbinding in.'),409
        if not status()['workerAvailable']:
            return jsonify(error='Installatieservice niet beschikbaar.'),503
        try:
            with queue_lock:
                for queued in (root/'queue').glob('*.json'):
                    result=root/'results'/queued.name
                    if not result.exists() or json.loads(result.read_text()).get('status') in ('queued','running'):
                        return jsonify(error='Er wordt al een installatie uitgevoerd. Wacht tot deze klaar is.'),409
                job_id=uuid.uuid4().hex
                payload={**selected,'id':job_id,'requestedBy':g.account['email'],'createdAt':time.time()}
                temporary=root/'queue'/f'{job_id}.tmp'
                temporary.write_text(json.dumps(payload),encoding='utf-8')
                os.chmod(temporary,0o640)
                os.replace(temporary,root/'queue'/f'{job_id}.json')
            return jsonify(id=job_id,status='queued'),202
        except (OSError,ValueError):
            return jsonify(error='De installatie kan niet worden klaargezet.'),503

    @app.get('/api/installations/jobs/<job_id>')
    def job(job_id):
        if not re.fullmatch('[a-f0-9]{32}',job_id):
            return jsonify(error='Onbekende installatie.'),404
        try:
            result=root/'results'/f'{job_id}.json'
            if result.is_file():
                return jsonify(json.loads(result.read_text()))
            if (root/'queue'/f'{job_id}.json').is_file():
                return jsonify(id=job_id,status='queued',message='Wachten op de installatieservice…')
            return jsonify(error='Onbekende installatie.'),404
        except (OSError,ValueError):
            return jsonify(error='De installatiestatus kan niet worden gelezen.'),503
