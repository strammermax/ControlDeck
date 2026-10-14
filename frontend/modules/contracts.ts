import type {DashboardItem} from "../lib/dashboards";
export type ModuleSettings = Extract<DashboardItem,{type:"module"}>["settings"];
export type ModuleViewProps = {settings:ModuleSettings;csrfToken:string};
export type ModuleSettingsProps = ModuleViewProps & {onChange:(settings:ModuleSettings)=>void};
