import {websiteFavicon, uploadDashboardIcon} from '../lib/app-icons.ts';
import test from 'node:test';
import assert from 'node:assert/strict';
import {dashboardRequest, firstSpace, placeItem, removeSection, configureItem, dashboardNavigation, dashboardItemView, filterDashboardApps} from '../lib/dashboards.ts';

const item = {id:'link', type:'link', sectionId:'apps', title:'Portal', url:'https://example.test', description:'', x:0,y:0,width:4,height:1};
const board = {id:'board',revision:1,title:'Werk',sections:[{id:'apps',title:'Apps',lane:'main',collapsed:false},{id:'rail',title:'Tools',lane:'left',collapsed:false}],items:[item]};
const app = {id:1,name:'Jellyfin',url:'https://media.example.test',description:'Films',collection:'Media',icon:'jellyfin.png',summary:[{label:'Films',value:12}]};
const reference = {id:'reference',sectionId:'apps',type:'app',appId:1,x:0,y:0,width:4,height:2};

test('dashboard app references normaal: resolve current source name, destination and counts',()=>{
  assert.equal(dashboardItemView(reference,[app]).title,'Jellyfin');
  const changed={...app,name:'Media nieuw',url:'https://new.example.test'};
  assert.equal(dashboardItemView(reference,[changed]).url,changed.url);
  assert.deepEqual(dashboardItemView(reference,[app]).summary,app.summary);
  assert.equal(dashboardItemView(item,[]).url,item.url);
});
test('dashboard app references boundary: removed source becomes unavailable without copied metadata',()=>{
  const view=dashboardItemView(reference,[]);
  assert.equal(view.available,false);assert.equal(view.url,null);assert.equal(view.summary.length,0);
  assert.equal(dashboardItemView(reference,[{...app,summary:[]}]).summary.length,0);
});
test('dashboard app references faal: stale copied fields cannot bypass the authorized catalog',()=>{
  const view=dashboardItemView({...reference,title:'Private',url:'https://private.example.test',summary:[{label:'Secret',value:1}]},[]);
  assert.equal(view.url,null);assert.equal(JSON.stringify(view).includes('Private'),false);assert.equal(JSON.stringify(view).includes('Secret'),false);
  assert.equal(dashboardItemView({...reference,appId:2},[app]).available,false);
});
test('dashboard app filter normaal: all words match name, group and description',()=>{
  assert.deepEqual(filterDashboardApps([app],'media JELLYFIN'),[app]);
});
test('dashboard app filter boundary: whitespace, empty catalog, Unicode and no matches',()=>{
  assert.deepEqual(filterDashboardApps([app],'  '),[app]);assert.deepEqual(filterDashboardApps([],''),[]);
  assert.equal(filterDashboardApps([{...app,name:'Één'}],'één').length,1);assert.deepEqual(filterDashboardApps([app],'unknown'),[]);
});
test('dashboard app filter faal: invalid queries rejected',()=>{
  for(const query of [null,1,'x'.repeat(201)]) assert.throws(()=>filterDashboardApps([app],query),TypeError);
});

test('dashboard navigation normaal: accepting discard opens the requested module',()=>{
  assert.equal(dashboardNavigation('dashboard','bookmarks',true,()=>true),'bookmarks');
});
test('dashboard navigation boundary: same page and non-editor navigation never prompt',()=>{
  const unexpected=()=>{throw Error('Unexpected prompt');};
  assert.equal(dashboardNavigation('dashboard','dashboard',true,unexpected),'dashboard');
  assert.equal(dashboardNavigation('dashboard','bookmarks',false,unexpected),'bookmarks');
  assert.equal(dashboardNavigation('bookmarks','dashboard',true,unexpected),'dashboard');
});
test('dashboard navigation faal: refusing discard retains the unfinished dashboard',()=>{
  assert.equal(dashboardNavigation('dashboard','bookmarks',true,()=>false),'dashboard');
});

test('dashboard configure regression: new tile ignored entered coordinates because auto-placement ran for absent previous item',()=>{
  const result=configureItem({...board,items:[]},{...item,x:4,y:2});
  assert.equal(result.items[0].x,4);assert.equal(result.items[0].y,2);
});
test('dashboard configure normaal: an existing tile moves to free space in its new group',()=>{
  const result=configureItem(board,{...item,sectionId:'rail',x:4});
  assert.equal(result.items[0].sectionId,'rail');assert.equal(result.items[0].x,0);
});
test('dashboard configure boundary: resizing in the current group retains its coordinates',()=>{
  assert.equal(configureItem(board,{...item,x:8,width:4}).items[0].x,8);
});
test('dashboard configure faal: overlapping form coordinates and missing group rejected',()=>{
  assert.throws(()=>configureItem(board,{...item,id:'new',x:0}),/bezet/);
  assert.throws(()=>configureItem(board,{...item,sectionId:'missing'}),RangeError);
});

test('dashboard placement normaal: move, resize, change group and add without mutation',()=>{
  assert.equal(placeItem(board,{...item,x:4}).items[0].x,4);
  assert.equal(placeItem(board,{...item,width:8,height:2}).items[0].width,8);
  assert.equal(placeItem(board,{...item,sectionId:'rail'}).items[0].sectionId,'rail');
  assert.equal(placeItem(board,{...item,id:'second',x:4}).items.length,2);
  assert.equal(board.items[0].x,0);
});
test('dashboard placement boundary: right and bottom edges, touching tiles',()=>{
  assert.equal(placeItem(board,{...item,x:0,y:94,width:12,height:6}).items[0].y,94);
  assert.equal(placeItem(board,{...item,id:'second',x:4}).items.length,2);
});
test('dashboard placement faal: invalid bounds, overlaps, absent group and item limit',()=>{
  for(const patch of [{x:-1},{x:9},{y:100},{width:0},{height:7},{x:0.5},{sectionId:'missing'}]) assert.throws(()=>placeItem(board,{...item,...patch}),RangeError);
  assert.throws(()=>placeItem(board,{...item,id:'other'}),/bezet/);
  const full={...board,items:Array.from({length:100},(_,y)=>({...item,id:`i-${y}`,y}))};
  assert.throws(()=>placeItem(full,{...item,id:'extra',sectionId:'rail'}),/100/);
});
test('dashboard space normaal: finds the next free cell and respects groups',()=>{
  assert.deepEqual(firstSpace(board,'apps'),{x:4,y:0});
  assert.deepEqual(firstSpace(board,'rail'),{x:0,y:0});
});
test('dashboard space boundary: full width, last row, full grid',()=>{
  assert.deepEqual(firstSpace(board,'rail',12,6),{x:0,y:0});
  const full={...board,items:Array.from({length:99},(_,y)=>({...item,id:`i-${y}`,width:12,y}))};
  assert.deepEqual(firstSpace(full,'apps',12),{x:0,y:99});
  assert.throws(()=>firstSpace({...full,items:[...full.items,{...item,id:'last',width:12,y:99}]},'apps'),/vol/);
});
test('dashboard space faal: unknown group and invalid dimensions',()=>{
  for (const [group,width,height] of [['missing',4,1],['apps',0,1],['apps',13,1],['apps',4,7],['apps',4,1.5]]) assert.throws(()=>firstSpace(board,group,width,height),RangeError);
});
test('dashboard groups normaal: remove empty group without mutating source',()=>{
  assert.equal(removeSection(board,'rail').sections.length,1); assert.equal(board.sections.length,2);
});
test('dashboard groups boundary: retain the last group',()=>{
  assert.throws(()=>removeSection({...board,sections:[board.sections[1]],items:[]},'rail'),/minstens/);
});
test('dashboard groups faal: occupied and unknown groups cannot disappear',()=>{
  assert.throws(()=>removeSection(board,'apps'),/tegels/); assert.throws(()=>removeSection(board,'missing'),/bestaat niet/);
});
test('dashboard request normaal: revision and CSRF sent when saving',async()=>{
  const previous=global.fetch;try{global.fetch=async(url,options)=>{assert.equal(url,'/api/dashboards/board');assert.equal(options.headers['X-CSRF-Token'],'csrf');assert.equal(JSON.parse(options.body).revision,1);return {ok:true,json:async()=>({dashboard:board})};};assert.deepEqual(await dashboardRequest('/board','csrf','PUT',board),{dashboard:board});}finally{global.fetch=previous;}
});
test('dashboard request boundary: GET has no mutation credentials and preserves abort signal',async()=>{
  const previous=global.fetch;const controller=new AbortController();try{global.fetch=async(url,options)=>{assert.equal(options.body,undefined);assert.equal(options.headers['X-CSRF-Token'],undefined);assert.equal(options.signal,controller.signal);return {ok:true,json:async()=>({dashboards:[],defaultId:null})};};assert.deepEqual(await dashboardRequest('','','GET',undefined,controller.signal),{dashboards:[],defaultId:null});}finally{global.fetch=previous;}
});
test('dashboard request faal: conflict, malformed error, network failure and unsafe paths',async()=>{
  const previous=global.fetch;try{
    global.fetch=async()=>({ok:false,json:async()=>({error:'Elders gewijzigd'})});await assert.rejects(()=>dashboardRequest('/board'),/Elders gewijzigd/);
    global.fetch=async()=>({ok:false,json:async()=>{throw Error('HTML');}});await assert.rejects(()=>dashboardRequest(),/niet beschikbaar/);
    global.fetch=async()=>{throw Error('Offline');};await assert.rejects(()=>dashboardRequest(),/Offline/);
    await assert.rejects(()=>dashboardRequest('/../accounts'),TypeError);
  }finally{global.fetch=previous;}
});


test('website favicon normal and boundary: destination origin only, custom port preserved',()=>{
 assert.equal(websiteFavicon('https://example.test/path?q=private'),'https://example.test/favicon.ico');
 assert.equal(websiteFavicon('http://host.test:8080/'),'http://host.test:8080/favicon.ico');
});
test('website favicon failure: reject credentials and active URLs',()=>{
 for(const url of ['', 'javascript:alert(1)', 'https://user:pass@example.test']) assert.equal(websiteFavicon(url),null);
});
test('PNG upload failure and boundary: wrong types, empty and oversized files rejected',async()=>{
 for(const file of [{type:'image/svg+xml',size:10},{type:'image/png',size:0},{type:'image/png',size:2097153}]) await assert.rejects(uploadDashboardIcon(file));
});
test('PNG upload normal: normalize and release image resources',async()=>{
 const oldBitmap=globalThis.createImageBitmap, oldDocument=globalThis.document;
 let closed=false, drawn=false;
 globalThis.createImageBitmap=async()=>({width:128,height:64,close(){closed=true;}});
 globalThis.document={createElement(){return {getContext(){return {drawImage(){drawn=true;}};},toDataURL(){return 'data:image/png;base64,test';}};}};
 try {assert.equal(await uploadDashboardIcon({type:'image/png',size:100}),'data:image/png;base64,test');assert.ok(closed&&drawn);}
 finally {globalThis.createImageBitmap=oldBitmap;globalThis.document=oldDocument;}
});

test('PNG upload boundary and failure: maximum file, image dimensions and decode errors',async()=>{
 const oldBitmap=globalThis.createImageBitmap,oldDocument=globalThis.document;let closed=0;
 globalThis.document={createElement(){return {getContext(){return {drawImage(){}};},toDataURL(){return 'data:image/png;base64,test';}};}};
 try {
  globalThis.createImageBitmap=async()=>({width:4096,height:4096,close(){closed++;}});
  assert.equal(await uploadDashboardIcon({type:'image/png',size:2097152}),'data:image/png;base64,test');
  globalThis.createImageBitmap=async()=>({width:4097,height:1,close(){closed++;}});
  await assert.rejects(uploadDashboardIcon({type:'image/png',size:100}));assert.equal(closed,2);
  globalThis.createImageBitmap=async()=>{throw new Error('decode');};
  await assert.rejects(uploadDashboardIcon({type:'image/png',size:100}));
 } finally {globalThis.createImageBitmap=oldBitmap;globalThis.document=oldDocument;}
});
