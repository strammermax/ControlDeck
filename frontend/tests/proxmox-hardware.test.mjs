import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {validateHardwareInventory,validateHardwareMonitor,hardwareSelection,hardwareTotals,sensorState} from '../lib/proxmox-hardware.ts';
const memory={node:'pve-amd',id:'0',slot:'DIMM 0',size:64*1024**3,type:'DDR5',configured_speed:'5600 MT/s',max_speed:'5600 MT/s',manufacturer:'Example'};
const sensor={node:'pve-amd',id:'0',kind:'cpu',name:'CPU Package',adapter:'PCI adapter',current:46.4,high:80,critical:95};
const node={name:'pve-amd',hardwareAvailable:true,memoryAvailable:true,sensorsAvailable:true,stale:false,cpu:{model:'Example CPU',l3_cache:'24 MiB',virtualization:'AMD-V',sockets:1,cores_per_socket:12,total_threads:24},motherboard:{manufacturer:'Example',model:'Board',bios:{vendor:'BIOS',version:'1.2',date:'2025-09-25'}},memory:[memory,{...memory,id:'1'}],sensors:[sensor],gpus:[{node:'pve-amd',name:'GPU',vendor:'Example',slot:'0000:01:00.0',driver:'amdgpu',type:'integrated'}],pci:[],usb:[],fans:[{node:'pve-amd',name:'Fan',speed:1200,unit:'RPM'}],power:[{node:'pve-amd',name:'CPU power',watts:24.5}]};
const data=()=>validateHardwareInventory({hardware:{nodes:[{name:'pve-amd',online:true},{name:'pve-nas',online:true}]},updatedAt:1000,stale:false});
test('hardware normal: node filtering and physical DIMM byte totals preserve duplicate slot labels',()=>{
 const monitor=validateHardwareMonitor({nodes:[node]});
 assert.equal(hardwareSelection(data(),monitor,'pve-amd').incomplete,false);
 assert.equal(hardwareSelection(data(),monitor,'pve-amd').monitor.length,1);
 assert.equal(hardwareSelection(data(),monitor).incomplete,true);
 assert.equal(hardwareTotals(monitor).memory,128*1024**3);assert.equal(hardwareTotals(monitor).hottest,46.4);
 assert.equal(sensorState(sensor),'normal');assert.equal(sensorState({...sensor,current:80}),'warning');assert.equal(sensorState({...sensor,current:95}),'critical');
});
test('hardware boundary: missing differs from zero, negative Celsius allowed, stale or removed nodes cannot claim completeness',()=>{
 assert.equal(sensorState({...sensor,current:null}),'unknown');assert.equal(sensorState({...sensor,current:0}),'normal');assert.equal(sensorState({...sensor,current:-5}),'normal');
 assert.equal(hardwareTotals([]).memory,null);assert.equal(hardwareTotals([{...node,stale:true}]).memory,null);
 assert.equal(hardwareTotals([{...node,memory:[{...memory,size:null}]}]).memory,null);
 const view=hardwareSelection(data(),[node,{...node,name:'old-node'}]);assert.equal(view.monitor.length,1);
 assert.equal(hardwareSelection(data(),[{...node,stale:true}],'pve-amd').incomplete,true);
 assert.equal(hardwareTotals([{...node,sensors:[{...sensor,current:0}]}]).hottest,0);
});
test('hardware rejection: invalid node, duplicate DIMM identity, wrong source, impossible temperature and nonfinite fields',()=>{
 for(const value of [null,{}, {hardware:{nodes:[{name:'bad/host',online:true}]},updatedAt:1,stale:false}])assert.throws(()=>validateHardwareInventory(value));
 for(const value of [null,{}, {nodes:[node,node]},{nodes:[{...node,memory:[memory,memory]}]},{nodes:[{...node,memory:[{...memory,node:'pve-nas'}]}]},{nodes:[{...node,sensors:[{...sensor,current:Infinity}]}]},{nodes:[{...node,sensors:[{...sensor,current:301}]}]},{nodes:[{...node,power:[{...node.power[0],watts:-1}]}]},{nodes:[{...node,loading:'true'}]}])assert.throws(()=>validateHardwareMonitor(value));
});
await loadBindings();
async function compile(path,replacements={}){
 let {code}=await transform(readFileSync(new URL(path,import.meta.url),'utf8'),{filename:path,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
 for(const name of ['react','react/jsx-runtime'])code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
 for(const [name,url] of Object.entries(replacements))code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(url)}`);
 code=code.replace(/import "\.\/proxmox-(?:guests|hardware)\.css";?/g,'');
 return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
}
const libURL=new URL('../lib/proxmox-hardware.ts',import.meta.url).href;
const guestURL=new URL('../lib/proxmox-guests.ts',import.meta.url).href;
const shared=await compile('../modules/proxmox/guest-cards.tsx',{'../../lib/proxmox-guests':guestURL,'./pve-tag-color':new URL('../modules/proxmox/pve-tag-color.ts',import.meta.url).href});
const cardsURL=await compile('../modules/proxmox/hardware-cards.tsx',{'./guest-cards':shared,'../../lib/proxmox-guests':guestURL,'../../lib/proxmox-hardware':libURL});
const ui=await import(cardsURL);
const page=await import(await compile('../components/proxmox-hardware.tsx',{'../lib/proxmox-hardware':libURL,'../modules/proxmox/hardware-cards':cardsURL}));
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));
test('actual ProxMenux hardware JSX: system columns, repeated DIMMs, grouped sensor, peripheral and power cards',()=>{
 const system=render(ui.SystemInformation,{node});for(const text of ['System Information','CPU','Motherboard','12 cores','24 MiB','AMD-V','pve-amd'])assert.ok(system.includes(text),text);
 const modules=render(ui.MemoryModules,{nodes:[node]});assert.equal((modules.match(/DIMM 0/g)||[]).length,2);assert.ok(modules.includes('128.0 GB'));
 const thermal=render(ui.ThermalMonitoring,{nodes:[node]});assert.ok(thermal.includes('46.4°C'));assert.ok(thermal.includes('Thermal Monitoring'));
 const gpu=render(ui.HardwareDevices,{title:'Graphics Cards',rows:[{...node.gpus[0],name:'<script>bad</script>'}],fields:[['driver','Driver']]});assert.ok(gpu.includes('&lt;script&gt;'));assert.ok(gpu.includes('amdgpu'));assert.ok(!gpu.includes('<script>'));
 const power=render(ui.HardwarePower,{nodes:[node]});assert.ok(power.includes('24.5 W'));assert.ok(power.includes('1200 RPM'));
});
test('actual hardware boundary/failure UI: unavailable node keeps unknown total and thermal alerts have text',()=>{
 const unknown=render(ui.SystemInformation,{node:{name:'pve-nas'}});assert.ok(unknown.includes('—'));
 const reading=render(ui.ThermalReading,{sensor:{...sensor,current:95}});assert.ok(reading.includes('Kritiek'));
 assert.ok(render(ui.ThermalReading,{sensor:{...sensor,current:null}}).includes('Onbekend'));
 const view=render(page.HardwareInventoryView,{data:data(),monitor:[node]});for(const text of ['Cluster','pve-amd','pve-nas','aria-pressed="true"','Niet alle hardwaremetingen','Geheugeninventaris ontbreekt'])assert.ok(view.includes(text),text);
 // Missing-node total regression: summing only the responding node must not look like a complete cluster total.
 assert.ok(view.includes('2 installed · —'));
 assert.ok(render(page.HardwareInventoryView,{data:data(),monitor:[]}).includes('Geen temperatuursensoren'));
 assert.ok(!/NaN|Infinity/.test(view));
});
