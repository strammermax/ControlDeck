import test from 'node:test';
import assert from 'node:assert/strict';
import {groupBookmarks} from '../lib/bookmark-layout.ts';
import {bookmarkIcon} from '../lib/bookmark-icons.ts';
const row=(id,name='Proxmox',collection='Infra',url='https://proxmox.com')=>({id,name,collection,url,description:'',tags:[]});
test('bookmark grouping normaal: collection columns preserve links and hostname',()=>{
 const result=groupBookmarks([row(1),row(2,'Plex','Media','https://www.plex.tv'),row(3,'Linkwarden','Infra')]);
 assert.deepEqual(result.map(group=>group.name),['Infra','Media']);assert.equal(result[0].links.length,2);assert.equal(result[1].links[0].hostname,'plex.tv');assert.equal(result[0].links[0].initials,'PR');
});
test('bookmark grouping boundary: empty, missing titles, unicode and repeated pages',()=>{
 assert.deepEqual(groupBookmarks([]),[]);const result=groupBookmarks([row(1,'',''),row(1),row(2,'\u{1F4DA} Links','')]);
 assert.equal(result[0].name,'Overige bookmarks');assert.equal(result[0].links.length,2);assert.equal(result[0].links[0].name,'proxmox.com');assert.equal(result[0].links[1].initials,'📚L');
});
test('bookmark grouping faal: malformed payload and unsafe destinations cannot render',()=>{
 assert.throws(()=>groupBookmarks(null));assert.deepEqual(groupBookmarks([null,row(1,'x','x','javascript:alert(1)'),row(2,'x','x','https://user:secret@example.com'),row(3,'x','x','invalid')]),[]);
});
test('automatic icons normaal: explicit Homepage icon, title and known domain',()=>{
 assert.equal(bookmarkIcon('Node','http://192.168.1.98','proxmox.png'),'/service-icons/proxmox.png');assert.equal(bookmarkIcon('Plex Server','http://192.168.1.129'),'/service-icons/plex.png');assert.equal(bookmarkIcon('Source','https://github.com/gethomepage/homepage'),'/service-icons/github.png');
});
test('automatic icons boundary: unsupported icon falls back, unknown site has no request',()=>{
 assert.equal(bookmarkIcon('ProxMenux pve-amd','http://192.168.1.98','mdi-monitor-dashboard'),'/service-icons/proxmox.png');assert.equal(bookmarkIcon('Private Notes','https://notes.example.test'),null);assert.equal(bookmarkIcon('Seerr','https://example.test'),'/service-icons/jellyseerr.png');
});
test('automatic icons faal: foreign URLs and paths cannot control asset destination',()=>{
 assert.equal(bookmarkIcon('Unknown','https://example.test','../../secret'),null);assert.equal(bookmarkIcon('Plex','javascript:alert(1)','plex.png'),null);assert.equal(bookmarkIcon('Plex','https://user:secret@example.com','plex.png'),null);assert.equal(bookmarkIcon(null,null),null);
});

test('bookmark initials regression: emoji titles must not split a UTF-16 surrogate',()=>{assert.equal(groupBookmarks([row(1,'📚 Links')])[0].links[0].initials,'📚L');});
