"""Native, shared startpage links stored in private JSON; no Homepage server required."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl
from flask import g, jsonify, request
from backend.auth import filter_configuration, database
from backend.configuration import load_config
from backend.linkwarden import save_private
from backend.auth import is_manager


def validate_homepage_link(value):
    if not isinstance(value,dict):raise ValueError('Ongeldige link.')
    fields={'name':300,'url':2048,'collection':200,'description':1000,'icon':100}
    result={}
    for key,limit in fields.items():
        text=value.get(key,'')
        if not isinstance(text,str) or len(text)>limit or any(ord(c)<32 for c in text):raise ValueError('Ongeldige linkgegevens.')
        result[key]=text.strip()
    if not result['name'] or not result['collection']:raise ValueError('Vul een titel en groep in.')
    try:
        url=urlsplit(result['url'])
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:raise ValueError('Ongeldig adres.')
        if any(re.search(r'token|api.?key|password|secret',key,re.I) for key,_ in parse_qsl(url.query)):raise ValueError('Geen geheimen in linkadressen.')
        _=url.port
    except ValueError:raise ValueError('Gebruik een HTTP- of HTTPS-adres zonder login of geheimen.') from None
    if result['icon'] and not re.fullmatch(r'[a-z0-9-]+(?:\.png)?',result['icon']):raise ValueError('Ongeldig icoon.')
    result['tags']=[]
    return result


def read_homepage_links(path):
    """Shared validated source for Homepage, personal dashboards and search."""
    if not path.exists():return []
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,list) or len(value)>500:raise ValueError('Ongeldige configuratie.')
    links=[];ids=set()
    for row in value:
        if not isinstance(row,dict) or type(row.get('id')) is not int or row['id']<=0 or row['id'] in ids:raise ValueError('Ongeldige link-ID.')
        links.append({'id':row['id'],**validate_homepage_link(row)});ids.add(row['id'])
    return links


def setup_homepage(app,configuration_path,data_dir):
    path=Path(data_dir)/'homepage/links.json'

    @app.before_request
    def homepage_access():
        if request.path.startswith('/api/homepage') and g.account is not None:
            if not any(m['id']=='bookmarks' for m in filter_configuration(load_config(configuration_path),g.account)['modules']):
                return jsonify(error='Geen toegang tot Bookmarks.'),403
            if request.method not in ('GET','HEAD','OPTIONS') and not is_manager(g.account):
                return jsonify(error='Beheerrechten vereist.'),403

    @app.route('/api/homepage/links',methods=['GET','POST'])
    @app.route('/api/homepage/links/<int:link_id>',methods=['PUT','DELETE'])
    def homepage_links(link_id=None):
        try:
            with database(Path(data_dir)/'users.sqlite3') as db:
                db.execute('BEGIN IMMEDIATE')
                links=read_homepage_links(path)
                if request.method in ('GET','HEAD'):return jsonify(links=links)
                # Capture the current high-water mark before deletion as well as
                # creation. Dashboard/integration references must never be retargeted.
                db.execute('UPDATE homepage_link_sequence SET last_id=MAX(last_id,?) WHERE singleton=1', (max((item['id'] for item in links),default=0),))
                if request.method=='POST':
                    if len(links)>=500:return jsonify(error='Maximaal 500 links toegestaan.'),400
                    row=validate_homepage_link(request.get_json(silent=True))
                    link_id=db.execute('SELECT last_id+1 FROM homepage_link_sequence WHERE singleton=1').fetchone()[0]
                    db.execute('UPDATE homepage_link_sequence SET last_id=? WHERE singleton=1',(link_id,))
                    row={'id':link_id,**row};links.append(row)
                else:
                    index=next((i for i,item in enumerate(links) if item['id']==link_id),None)
                    if index is None:return jsonify(error='Link niet gevonden.'),404
                    if request.method=='DELETE':links.pop(index)
                    else:links[index]={'id':link_id,**validate_homepage_link(request.get_json(silent=True))}
                # A private previous version allows manual recovery after an edit or deletion.
                if path.exists():save_private(path.with_name('links.previous.json'),json.loads(path.read_text(encoding='utf-8')))
                save_private(path,links)
                return jsonify(links=links),201 if request.method=='POST' else 200
        except (ValueError,TypeError):return jsonify(error='Ongeldige Homepage-link of configuratie.'),400
        except OSError:return jsonify(error='Homepage-links konden niet worden opgeslagen of geladen.'),503
