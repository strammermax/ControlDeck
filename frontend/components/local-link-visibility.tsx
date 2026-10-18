"use client";
import {useLayoutEffect} from "react";
import {applyLocalLinkVisibility} from "../lib/local-links";
export function LocalLinkVisibility({hide}:{hide:boolean}) {
 useLayoutEffect(()=>{
  applyLocalLinkVisibility(document,hide);
  const observer=new MutationObserver(()=>applyLocalLinkVisibility(document,hide));
  observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:["href","src"]});
  return()=>{observer.disconnect();applyLocalLinkVisibility(document,false);};
 },[hide]);
 return null;
}
