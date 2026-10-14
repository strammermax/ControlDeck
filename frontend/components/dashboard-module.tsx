"use client";
import {moduleComponents} from "../modules/registry";
import {dashboardModules} from "../lib/dashboard-modules";
import type {ModuleViewProps,ModuleSettingsProps} from "../modules/contracts";

export function DashboardModule({moduleId,settings,csrfToken,permissions}:ModuleViewProps&{moduleId:string;permissions:string[]}) {
  const module=moduleComponents(moduleId),definition=dashboardModules.find(value=>value.id===moduleId);
  if(definition&&!permissions.includes(definition.permission)) return <p className="cd-dashboard-unavailable">Je hebt geen toegang tot deze module.</p>;
  if(!module||!definition) return <p>Deze module is niet beschikbaar.</p>;
  return <div className="cd-dashboard-module"><header><strong>{definition.title}</strong></header><module.View settings={settings} csrfToken={csrfToken}/></div>;
}

export function DashboardModuleSettings({moduleId,...props}:ModuleSettingsProps&{moduleId:string}) {
  const module=moduleComponents(moduleId);
  return module?<module.Settings {...props}/>:<p>Deze module is niet beschikbaar.</p>;
}
