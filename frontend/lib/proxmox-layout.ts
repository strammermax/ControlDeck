import {mergeLayout, type GridBounds} from "./layout-grid.ts";
import {groupCells, type PageLayoutCell} from "./page-layouts.ts";

export const proxmoxPageGrid: GridBounds = {columns: 12, maxHeight: 12, maxRows: 300};
/** Default size per Proxmox widget; the default order is the order of this list. */
export const proxmoxWidgetSizes: Record<string, {width: number; height: number}> = {
  health: {width: 12, height: 4}, guests: {width: 6, height: 4}, "nodes-cpu": {width: 6, height: 3}, "nodes-memory": {width: 6, height: 3},
  "task-categories": {width: 6, height: 4}, "task-nodes": {width: 6, height: 4}, sdn: {width: 6, height: 3}, tasks: {width: 12, height: 6},
};

/** Saved personal cells for the widgets shown now; unknown widgets get a 6×3 tile. */
export function proxmoxPageCells(ids: string[], saved: PageLayoutCell[]): PageLayoutCell[] {
  return mergeLayout(ids, groupCells(saved, "main"), id => proxmoxWidgetSizes[id] ?? {width: 6, height: 3}, proxmoxPageGrid).map(cell => ({...cell, group: "main"}));
}
