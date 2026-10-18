import type {Bookmark} from './linkwarden';
import {firstFreeCell,layoutOrder,mergeLayout,placeCell,type GridBounds} from './layout-grid.ts';
import {groupCells,type PageLayoutCell} from './page-layouts.ts';

export type BookmarkTile = Bookmark & {hostname:string;initials:string};
export type BookmarkGroup = {name:string;links:BookmarkTile[]};

/** Group only safe links; repeated pagination rows must not become duplicate tiles. */
export function groupBookmarks(links:Bookmark[]):BookmarkGroup[] {
  if(!Array.isArray(links))throw new TypeError('Ongeldig bookmarkoverzicht.');
  const groups=new Map<string,BookmarkGroup>();
  const ids=new Set<number>();
  for(const item of links){
    if(!item||!Number.isInteger(item.id)||ids.has(item.id)||typeof item.url!=='string')continue;
    let url:URL;
    try{url=new URL(item.url);}catch{continue;}
    if(!['https:','http:'].includes(url.protocol)||url.username||url.password)continue;
    const name=typeof item.name==='string'&&item.name.trim()?item.name.trim():url.hostname;
    const group=typeof item.collection==='string'&&item.collection.trim()?item.collection.trim():'Overige bookmarks';
    const words=name.split(/\s+/u);
    const initials=(words.length>1?Array.from(words[0])[0]+Array.from(words[1])[0]:Array.from(name).slice(0,2).join('')).toLocaleUpperCase('nl');
    const tile={...item,name,hostname:url.host.replace(/^www\./,''),initials};
    if(!groups.has(group))groups.set(group,{name:group,links:[]});
    groups.get(group)!.links.push(tile);ids.add(item.id);
  }
  return [...groups.values()];
}

/** Links inside one bookmark group: two columns, a full-width tile of one row by default. */
export const bookmarkGrid:GridBounds={columns:2,maxHeight:4,maxRows:300};

/** Personal regrouping: a link whose saved cell sits in another existing group is shown there.
 * The shared collection never changes; unknown target groups are ignored. Empty groups stay (drop targets). */
export function personalGroups(groups:BookmarkGroup[],saved:PageLayoutCell[]):BookmarkGroup[] {
  const names=new Set(groups.map(group=>group.name));
  const target=new Map<string,string>();
  for(const cell of Array.isArray(saved)?saved:[])if(cell&&names.has(cell.group)&&!target.has(cell.id))target.set(cell.id,cell.group);
  const result=groups.map(group=>({name:group.name,links:[] as BookmarkTile[]}));
  const byName=new Map(result.map(group=>[group.name,group]));
  for(const group of groups)for(const link of group.links)byName.get(target.get(String(link.id))??group.name)!.links.push(link);
  return result;
}

/** Personal positions for every visible link, per (personal) group; new links flow into free space. */
export function bookmarkLayout(groups:BookmarkGroup[],saved:PageLayoutCell[]):PageLayoutCell[] {
  return personalGroups(groups,saved).flatMap(group=>mergeLayout(group.links.map(link=>String(link.id)),groupCells(saved,group.name),()=>({width:2,height:1}),bookmarkGrid).map(cell=>({...cell,group:group.name})));
}

/** Move one link's cell to another group: at the wanted position when free, else the first free place. */
export function moveBookmark(cells:PageLayoutCell[],id:string,toGroup:string,at?:{x:number;y:number}):PageLayoutCell[] {
  const current=cells.find(cell=>cell.id===id);
  if(!current)throw new RangeError('Onbekende bookmark.');
  if(typeof toGroup!=='string'||!toGroup)throw new RangeError('Onbekende groep.');
  const rest=cells.filter(cell=>cell.id!==id);
  const siblings=groupCells(rest,toGroup);
  const size={width:Math.min(current.width,bookmarkGrid.columns),height:Math.min(current.height,bookmarkGrid.maxHeight)};
  let position=firstFreeCell(siblings,size.width,size.height,bookmarkGrid);
  if(at){
    const wanted={x:Math.max(0,Math.min(at.x,bookmarkGrid.columns-size.width)),y:Math.max(0,at.y)};
    try{placeCell(siblings,{id,...size,...wanted},bookmarkGrid);position=wanted;}catch{/* Occupied: keep the first free place. */}
  }
  return [...rest,{id,group:toGroup,...size,...position}];
}

/** Search results and read-only lists follow the personal reading order. */
export function orderedLinks(group:BookmarkGroup,cells:PageLayoutCell[]):BookmarkTile[] {
  const order=layoutOrder(groupCells(cells,group.name));
  const rank=(id:number)=>{const index=order.indexOf(String(id));return index<0?Number.MAX_SAFE_INTEGER:index;};
  return [...group.links].sort((a,b)=>rank(a.id)-rank(b.id));
}
