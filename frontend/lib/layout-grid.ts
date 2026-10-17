/** Shared grid rules for every movable/resizable page layout (dashboard, bookmarks, Proxmox, …).
 * Coordinates are logical cells; servers validate the same bounds independently. */
export type GridCell = {id: string; x: number; y: number; width: number; height: number};
export type GridBounds = {columns: number; maxHeight: number; maxRows: number};

export function cellsOverlap(a: GridCell, b: GridCell): boolean {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

export function validBounds(bounds: GridBounds): boolean {
  return [bounds.columns, bounds.maxHeight, bounds.maxRows].every(value => Number.isInteger(value) && value >= 1) && bounds.columns <= 24 && bounds.maxRows <= 500;
}

export function cellFits(cell: GridCell, bounds: GridBounds): boolean {
  return [cell.x, cell.y, cell.width, cell.height].every(Number.isInteger) && cell.x >= 0 && cell.y >= 0 && cell.width >= 1 && cell.height >= 1 &&
    cell.height <= bounds.maxHeight && cell.x + cell.width <= bounds.columns && cell.y + cell.height <= bounds.maxRows;
}

/** Replace or append one cell; refuses positions outside the grid or on top of another cell. */
export function placeCell(cells: GridCell[], cell: GridCell, bounds: GridBounds): GridCell[] {
  if (!validBounds(bounds) || typeof cell?.id !== "string" || !cell.id || !cellFits(cell, bounds)) throw new RangeError("De tegel past niet op deze plaats.");
  if (cells.some(other => other.id !== cell.id && cellsOverlap(cell, other))) throw new RangeError("Deze plaats is al bezet. Kies een vrije plaats.");
  return cells.some(other => other.id === cell.id) ? cells.map(other => other.id === cell.id ? {...cell} : other) : [...cells, {...cell}];
}

/** First free top-left position, scanning rows top to bottom. */
export function firstFreeCell(cells: GridCell[], width: number, height: number, bounds: GridBounds): {x: number; y: number} {
  if (!validBounds(bounds) || !Number.isInteger(width) || width < 1 || width > bounds.columns || !Number.isInteger(height) || height < 1 || height > bounds.maxHeight) {
    throw new RangeError("Ongeldige tegelgrootte.");
  }
  for (let y = 0; y <= bounds.maxRows - height; y++) {
    for (let x = 0; x <= bounds.columns - width; x++) {
      if (!cells.some(other => cellsOverlap({id: "", x, y, width, height}, other))) return {x, y};
    }
  }
  throw new RangeError("Deze groep is vol.");
}

/** Clamp a requested size to the grid edge and height limit (collisions are checked by placeCell). */
export function resizedCell(cell: GridCell, width: number, height: number, bounds: GridBounds): GridCell {
  return {...cell, width: Math.max(1, Math.min(bounds.columns - cell.x, Math.round(width))), height: Math.max(1, Math.min(bounds.maxHeight, bounds.maxRows - cell.y, Math.round(height)))};
}

/** Map a pointer position inside the grid element to a clamped top-left cell for the given size. */
export function pointerCell(rect: {left: number; top: number; width: number}, clientX: number, clientY: number, cell: GridCell, bounds: GridBounds, rowPitch: number, gap: number, grab = {x: 0, y: 0}): {x: number; y: number} {
  const columnPitch = (rect.width + gap) / bounds.columns;
  const x = Math.floor((clientX - rect.left) / columnPitch) - grab.x;
  const y = Math.floor((clientY - rect.top) / rowPitch) - grab.y;
  return {x: Math.max(0, Math.min(bounds.columns - cell.width, x)), y: Math.max(0, Math.min(bounds.maxRows - cell.height, y))};
}

/** Combine a saved layout with the items that exist now: saved cells for known ids stay put,
 * unknown/invalid/colliding saved cells are dropped and new items flow into the first free space. */
export function mergeLayout(ids: string[], saved: GridCell[], size: (id: string) => {width: number; height: number}, bounds: GridBounds): GridCell[] {
  const present = new Set(ids);
  let cells: GridCell[] = [];
  for (const cell of Array.isArray(saved) ? saved : []) {
    if (!cell || !present.has(cell.id) || cells.some(other => other.id === cell.id)) continue;
    try { cells = placeCell(cells, {id: cell.id, x: cell.x, y: cell.y, width: cell.width, height: cell.height}, bounds); } catch { /* Re-flow below. */ }
  }
  for (const id of ids) {
    if (cells.some(cell => cell.id === id)) continue;
    const wanted = size(id);
    const width = Math.max(1, Math.min(bounds.columns, wanted.width)), height = Math.max(1, Math.min(bounds.maxHeight, wanted.height));
    cells = [...cells, {id, width, height, ...firstFreeCell(cells, width, height, bounds)}];
  }
  return cells;
}

/** Reading order (row first) for lists, search results and narrow screens. */
export function layoutOrder(cells: GridCell[]): string[] {
  return [...cells].sort((a, b) => a.y - b.y || a.x - b.x).map(cell => cell.id);
}

export function layoutRows(cells: GridCell[], minimum = 1): number {
  return Math.max(minimum, ...cells.map(cell => cell.y + cell.height));
}
