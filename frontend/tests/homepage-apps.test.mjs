import test from 'node:test';
import assert from 'node:assert/strict';
import {homepageApps,searchApps,appDefaults} from '../lib/homepage-apps.ts';
test('Homepage app selection normaal: catalog search fills brand and icon',()=>{assert.equal(searchApps('Jellyfin')[0].name,'Jellyfin');assert.equal(appDefaults('radarr').icon,'radarr');assert.equal(appDefaults('jellyfin').apiSupported,true);assert.equal(appDefaults('plex').apiSupported,false);});
test('Homepage app selection boundary: all apps, whitespace and no matches',()=>{assert.equal(searchApps(' ').length,homepageApps.length);assert.ok(homepageApps.length>=80);assert.deepEqual(searchApps('there-is-no-such-app-xyz'),[]);assert.equal(new Set(homepageApps.map(app=>app.id)).size,homepageApps.length);});
test('Homepage app selection faal: invalid choices cannot invent integrations',()=>{assert.throws(()=>appDefaults('fake'));assert.throws(()=>searchApps(null));assert.ok(homepageApps.every(app=>/^[a-z0-9-]+$/.test(app.icon)));});

test("Homepage catalog regression: upstream icon underscores and mock entries cannot create invalid links",()=>{assert.equal(appDefaults("aria2").icon,"aria2");assert.ok(!homepageApps.some(app=>app.id==="mock"));});

test("Homepage catalog regression: authentication header names must not replace application names",()=>{for(const [id,name] of [["plex","Plex"],["radarr","Radarr"],["autobrr","Autobrr"],["emby","Emby"]])assert.equal(appDefaults(id).name,name);});
