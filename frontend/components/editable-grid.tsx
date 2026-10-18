"use client";
import {useRef, type CSSProperties, type ReactNode} from "react";
import {layoutRows, placeCell, pointerCell, resizedCell, type GridBounds, type GridCell} from "../lib/layout-grid";
import "./editable-grid.css";

type Gesture = {kind: "move" | "resize"; start: GridCell[]; cell: GridCell; x: number; y: number; grab: {x: number; y: number}; target: HTMLElement | null};

/** One reusable grid: tiles keep their cell in view mode; in edit mode a handle moves a tile and
 * the corner resizes it (pointer, touch and arrow keys). Collisions keep the last valid layout.
 * With `group` and `onTransfer`, a tile dropped on another grid of the same page moves to that group. */
export function EditableGrid({cells, bounds, editing, onChange, render, label, rowHeight = 72, gap = 12, className = "", group, onTransfer}: {
  cells: GridCell[]; bounds: GridBounds; editing: boolean; onChange: (cells: GridCell[]) => void;
  render: (id: string) => ReactNode; label: (id: string) => string; rowHeight?: number; gap?: number; className?: string;
  group?: string; onTransfer?: (id: string, group: string, at: {x: number; y: number}) => void;
}) {
  const gesture = useRef<Gesture | null>(null);
  const grid = useRef<HTMLDivElement>(null);
  const attempt = (next: () => GridCell[]) => { try { onChange(next()); } catch { /* Keep the last valid layout. */ } };
  const mark = (target: HTMLElement | null) => {
    const current = gesture.current; if (!current || current.target === target) return;
    current.target?.removeAttribute("data-drop-target");
    target?.setAttribute("data-drop-target", "true");
    current.target = target;
  };
  const begin = (kind: Gesture["kind"], cell: GridCell, event: React.PointerEvent<HTMLButtonElement>) => {
    const rect = grid.current?.getBoundingClientRect(); if (!rect) return;
    const at = pointerCell(rect, event.clientX, event.clientY, {...cell, width: 1, height: 1}, bounds, rowHeight + gap, gap);
    gesture.current = {kind, start: cells, cell, x: event.clientX, y: event.clientY, grab: {x: at.x - cell.x, y: at.y - cell.y}, target: null};
    event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault();
  };
  const otherGrid = (event: React.PointerEvent): HTMLElement | null => {
    if (!onTransfer || typeof document === "undefined") return null;
    const found = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-layout-group]") ?? null;
    return found && found !== grid.current ? found : null;
  };
  const move = (event: React.PointerEvent) => {
    const current = gesture.current, rect = grid.current?.getBoundingClientRect(); if (!current || !rect) return;
    if (current.kind === "move") {
      const other = otherGrid(event);
      mark(other);
      if (other) return;
      const at = pointerCell(rect, event.clientX, event.clientY, current.cell, bounds, rowHeight + gap, gap, current.grab);
      attempt(() => placeCell(current.start, {...current.cell, ...at}, bounds));
    } else {
      const pitch = (rect.width + gap) / bounds.columns;
      attempt(() => placeCell(current.start, resizedCell(current.cell, current.cell.width + (event.clientX - current.x) / pitch, current.cell.height + (event.clientY - current.y) / (rowHeight + gap), bounds), bounds));
    }
  };
  const end = (event: React.PointerEvent) => {
    const current = gesture.current; gesture.current = null;
    if (!current) return;
    const target = current.target;
    target?.removeAttribute("data-drop-target");
    const name = target?.dataset.layoutGroup;
    if (current.kind === "move" && target && name && onTransfer) {
      onChange(current.start);
      onTransfer(current.cell.id, name, pointerCell(target.getBoundingClientRect(), event.clientX, event.clientY, current.cell, bounds, rowHeight + gap, gap, current.grab));
    }
  };
  const cancel = () => { const current = gesture.current; current?.target?.removeAttribute("data-drop-target"); if (current) onChange(current.start); gesture.current = null; };
  const keys = (kind: Gesture["kind"], cell: GridCell) => (event: React.KeyboardEvent) => {
    const delta = ({ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]} as Record<string, number[]>)[event.key]; if (!delta) return;
    event.preventDefault();
    attempt(() => placeCell(cells, kind === "move" ? {...cell, x: cell.x + delta[0], y: cell.y + delta[1]} : {...cell, width: cell.width + delta[0], height: cell.height + delta[1]}, bounds));
  };
  return <div ref={grid} className={`cd-layout-grid ${className}`} data-editing={editing} data-layout-group={group}
    style={{"--layout-columns": bounds.columns, "--layout-rows": layoutRows(cells, editing ? 2 : 1), "--layout-row": `${rowHeight}px`, "--layout-gap": `${gap}px`} as CSSProperties}>
    {cells.map(cell => <div key={cell.id} className="cd-layout-cell" style={{gridColumn: `${cell.x + 1} / span ${cell.width}`, gridRow: `${cell.y + 1} / span ${cell.height}`, order: cell.y * bounds.columns + cell.x}}>
      {editing && <button type="button" className="cd-layout-move" aria-label={`${label(cell.id)} verplaatsen`} title={onTransfer ? "Sleep om te verplaatsen, ook naar een andere groep; pijltjestoetsen werken ook" : "Sleep om te verplaatsen; pijltjestoetsen werken ook"}
        onPointerDown={event => begin("move", cell, event)} onPointerMove={move} onPointerUp={end} onPointerCancel={cancel} onKeyDown={keys("move", cell)}>⠿</button>}
      <div className="cd-layout-content" inert={editing}>{render(cell.id)}</div>
      {editing && <button type="button" className="cd-layout-resize" aria-label={`${label(cell.id)} vergroten of verkleinen`} title="Sleep voor formaat; pijltjestoetsen werken ook"
        onPointerDown={event => begin("resize", cell, event)} onPointerMove={move} onPointerUp={end} onPointerCancel={cancel} onKeyDown={keys("resize", cell)}>↘</button>}
    </div>)}
    {editing && !cells.length && <p className="cd-layout-empty">Sleep hier een tegel naartoe.</p>}
  </div>;
}
