/** A display preference; original documents and authorization are untouched. */
export function isHomeLink(value:string,base:string):boolean {
 if(typeof value!=="string"||!value||value.startsWith("#")||(value.startsWith("/")&&!value.startsWith("//")))return false;
 try{const url=new URL(value,base),host=url.hostname.toLowerCase().replace(/\.$/,"");return ["http:","https:"].includes(url.protocol)&&(host==="home"||host.endsWith(".home"));}catch{return false;}
}
export function hideLocalLinks(enabled:boolean|undefined,isLocal:boolean|undefined) {
 return enabled!==false&&isLocal!==true;
}
export function applyLocalLinkVisibility(root:Document,hide:boolean) {
 root.querySelectorAll("[data-cd-local-link-hidden]").forEach(node=>node.removeAttribute("data-cd-local-link-hidden"));
 if(!hide)return;
 root.querySelectorAll("a[href],iframe[src]").forEach(node=>{
  const url=node.getAttribute(node.tagName==="IFRAME"?"src":"href")||"";
  if(isHomeLink(url,root.baseURI)){
   const tile=node.closest(".cd-dashboard-tile:not(.cd-dashboard-module-tile)");
   const row=node.closest("li");
   const target=tile||row||node;
   target.setAttribute("data-cd-local-link-hidden","");
  }
 });
}
