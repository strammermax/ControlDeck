export const trafficPeriods={hour:"1 uur",day:"24 uur",week:"7 dagen",month:"30 dagen",year:"1 jaar"} as const;
export type TrafficPeriod=keyof typeof trafficPeriods;
export type TrafficHistoryNode={name:string;loading?:boolean;stale?:boolean;error?:string;updatedAt?:number;historyAvailable?:boolean;timeframe?:TrafficPeriod;step?:number;history?:{time:number;received:number|null;sent:number|null}[]};
export type TrafficPoint={time:number;received:number|null;sent:number|null};
const amount=(n:unknown)=>n===null||typeof n==="number"&&Number.isFinite(n)&&n>=0&&n<=Number.MAX_SAFE_INTEGER;
export function validateTrafficHistory(value:unknown,period:TrafficPeriod):TrafficHistoryNode[] {
 const rows=(value as {nodes?:TrafficHistoryNode[]}|null)?.nodes;
 if(!Array.isArray(rows)||rows.length>64)throw new Error("Ongeldige netwerkhistorie.");
 for(const n of rows){
  if(!n||typeof n.name!=="string"||!/^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(n.name)||[n.loading,n.stale,n.historyAvailable].some(v=>v!==undefined&&typeof v!=="boolean")||n.error!==undefined&&(typeof n.error!=="string"||n.error.length>512)||n.updatedAt!==undefined&&!amount(n.updatedAt))throw new Error("Ongeldige historie-node.");
  if(n.history!==undefined){
   if(n.timeframe!==period||!Number.isInteger(n.step)||n.step!<1||n.step!>86400||!Array.isArray(n.history)||n.history.length>5000||n.history.some(p=>!p||!Number.isInteger(p.time)||p.time<=0||p.time>1e11||!amount(p.received)||!amount(p.sent))||new Set(n.history.map(p=>p.time)).size!==n.history.length)throw new Error("Ongeldige historische meetpunten.");
  }
 }
 if(new Set(rows.map(n=>n.name)).size!==rows.length)throw new Error("Dubbele historie-node.");
 return rows;
}
/** Integrate RRD byte/s averages over equal intervals; gaps remain gaps, never zero. */
export function trafficSeries(sources:TrafficHistoryNode[],names:string[],period:TrafficPeriod) {
 const nodes=sources.filter(n=>names.includes(n.name)&&n.timeframe===period),known=nodes.filter(n=>n.historyAvailable&&n.history?.length&&n.step);
 const incomplete=names.some(name=>!nodes.some(n=>n.name===name&&n.historyAvailable&&!n.loading&&!n.stale&&!n.error));
 if(!known.length)return {points:[] as TrafficPoint[],step:0,incomplete};
 const step=Math.max(...known.map(n=>n.step!));
 const starts=known.map(n=>n.history!.reduce((min,p)=>Math.min(min,p.time),Infinity)+step-n.step!),ends=known.map(n=>n.history!.reduce((max,p)=>Math.max(max,p.time),0));
 const start=Math.ceil(Math.max(...starts)/step)*step,end=Math.floor(Math.min(...ends)/step)*step;
 if((end-start)/step>5000)return {points:[] as TrafficPoint[],step,incomplete:true};
 const buckets=new Map<string,Map<number,{received:number;sent:number;rxKnown:boolean;txKnown:boolean;count:number}>>();
 for(const node of known){
  const map=new Map<number,{received:number;sent:number;rxKnown:boolean;txKnown:boolean;count:number}>();buckets.set(node.name,map);
  if(step%node.step!!==0)continue;
  for(const p of node.history!){
   const endTime=Math.ceil(p.time/step)*step;
   const b=map.get(endTime)??{received:0,sent:0,rxKnown:true,txKnown:true,count:0};
   b.count++;b.received+=(p.received??0)*node.step!;b.sent+=(p.sent??0)*node.step!;
   b.rxKnown&&=p.received!==null;b.txKnown&&=p.sent!==null;map.set(endTime,b);
  }
 }
 const points:TrafficPoint[]=[];
 for(let time=start;time<=end;time+=step){
  let received=0,sent=0,rxKnown=names.length>0,txKnown=names.length>0;
  for(const name of names){
   const node=known.find(n=>n.name===name),bucket=buckets.get(name)?.get(time),complete=!!node&&!!bucket&&bucket.count===step/node.step!;
   rxKnown&&=complete&&bucket!.rxKnown;txKnown&&=complete&&bucket!.txKnown;
   received+=bucket?.received??0;sent+=bucket?.sent??0;
  }
  points.push({time,received:rxKnown?received/1024**3:null,sent:txKnown?sent/1024**3:null});
 }
 return {points,step,incomplete:incomplete||points.some(p=>p.received===null||p.sent===null)};
}
export function trafficTick(time:number,period:TrafficPeriod) {
 return new Date(time*1000).toLocaleString("nl-NL",period==="hour"||period==="day"?{hour:"2-digit",minute:"2-digit"}:period==="year"?{month:"short",year:"2-digit"}:{day:"2-digit",month:"short",...(period==="week"?{hour:"2-digit" as const}:{})});
}
