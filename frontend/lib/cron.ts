/** Small cron toolkit for the Cronjobs module: parse, describe in Dutch, next/previous runs, missed runs, schedule picker. */
type Parsed = { minute: Set<number>; hour: Set<number>; dom: Set<number>; month: Set<number>; dow: Set<number>; domAny: boolean; dowAny: boolean };

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
// Four years plus a day: a leap-day schedule ("0 12 29 2 *") can be up to four years away.
const SEARCH_DAYS = 4 * 366;
const DAY_NAMES = ["zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"];
const SPECIAL: Record<string, string> = { "@hourly": "0 * * * *", "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@weekly": "0 0 * * 0", "@monthly": "0 0 1 * *", "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *" };

function field(text: string, min: number, max: number, names: string[] = [], offset = 0): Set<number> | null {
  const values = new Set<number>();
  const number = (token: string) => {
    const index = names.indexOf(token.toLowerCase());
    if (index >= 0) return index + offset;
    return /^\d+$/.test(token) ? Number(token) : NaN;
  };
  for (const part of text.split(",")) {
    const [range, stepText] = part.split("/");
    const step = stepText === undefined ? 1 : Number(stepText);
    if (!Number.isInteger(step) || step < 1 || (stepText !== undefined && !/^\d+$/.test(stepText))) return null;
    let start: number, end: number;
    if (range === "*") { start = min; end = max; }
    else if (range.includes("-")) { const [a, b] = range.split("-"); start = number(a); end = number(b); }
    else { start = number(range); end = stepText === undefined ? start : max; }
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < min || end > max || start > end) return null;
    for (let value = start; value <= end; value += step) values.add(value);
  }
  return values.size ? values : null;
}

export function parseCron(expression: string): Parsed | null {
  if (typeof expression !== "string") return null;
  const text = SPECIAL[expression.trim()] ?? expression.trim();
  const parts = text.split(/\s+/);
  if (parts.length !== 5) return null;
  const minute = field(parts[0], 0, 59), hour = field(parts[1], 0, 23), dom = field(parts[2], 1, 31);
  const month = field(parts[3], 1, 12, MONTHS, 1), dowRaw = field(parts[4], 0, 7, DAYS);
  if (!minute || !hour || !dom || !month || !dowRaw) return null;
  const dow = new Set([...dowRaw].map(day => day % 7));
  return { minute, hour, dom, month, dow, domAny: parts[2] === "*", dowAny: parts[4] === "*" };
}

function dayMatches(date: Date, p: Parsed): boolean {
  const domOk = p.dom.has(date.getDate()), dowOk = p.dow.has(date.getDay());
  if (p.domAny && p.dowAny) return true;
  if (p.domAny) return dowOk;
  if (p.dowAny) return domOk;
  return domOk || dowOk; // standard cron: either restriction may match
}

/** Next `count` run times after `from` (browser time zone). Searches four years ahead so 29 February is always found. */
export function nextRuns(expression: string, from: Date, count = 5): Date[] {
  const p = parseCron(expression);
  if (!p) return [];
  const runs: Date[] = [];
  const date = new Date(from.getTime());
  date.setSeconds(0, 0);
  date.setMinutes(date.getMinutes() + 1);
  const limit = from.getTime() + SEARCH_DAYS * 86400_000;
  while (runs.length < count && date.getTime() <= limit) {
    if (!p.month.has(date.getMonth() + 1)) { date.setMonth(date.getMonth() + 1, 1); date.setHours(0, 0, 0, 0); continue; }
    if (!dayMatches(date, p)) { date.setDate(date.getDate() + 1); date.setHours(0, 0, 0, 0); continue; }
    if (!p.hour.has(date.getHours())) { date.setHours(date.getHours() + 1, 0, 0, 0); continue; }
    if (p.minute.has(date.getMinutes())) runs.push(new Date(date.getTime()));
    date.setMinutes(date.getMinutes() + 1);
  }
  return runs;
}

/** Last run time at or before `before`, searching up to four years back. */
export function previousRun(expression: string, before: Date): Date | null {
  const p = parseCron(expression);
  if (!p) return null;
  const date = new Date(before.getTime());
  date.setSeconds(0, 0);
  const limit = before.getTime() - SEARCH_DAYS * 86400_000;
  while (date.getTime() >= limit) {
    if (!p.month.has(date.getMonth() + 1)) { date.setDate(0); date.setHours(23, 59, 0, 0); continue; }
    if (!dayMatches(date, p)) { date.setDate(date.getDate() - 1); date.setHours(23, 59, 0, 0); continue; }
    if (!p.hour.has(date.getHours())) { date.setHours(date.getHours() - 1, 59, 0, 0); continue; }
    if (p.minute.has(date.getMinutes())) return date;
    date.setMinutes(date.getMinutes() - 1);
  }
  return null;
}

const pad = (value: number) => String(value).padStart(2, "0");
const single = (text: string) => /^\d+$/.test(text);

/** Dutch description for common schedules; anything else is shown as the raw expression. */
export function describeCron(expression: string): string {
  const text = SPECIAL[expression?.trim()] ?? expression?.trim();
  if (!parseCron(text)) return "Ongeldig schema";
  const [m, h, dom, mon, dow] = text.split(/\s+/);
  const at = single(m) && single(h) ? `om ${pad(Number(h))}:${pad(Number(m))}` : null;
  if (text === "* * * * *") return "Elke minuut";
  if (/^\*\/\d+$/.test(m) && h === "*" && dom === "*" && mon === "*" && dow === "*") return `Elke ${m.slice(2)} minuten`;
  if (single(m) && h === "*" && dom === "*" && mon === "*" && dow === "*") return `Elk uur op minuut ${Number(m)}`;
  if (single(m) && /^\*\/\d+$/.test(h) && dom === "*" && mon === "*" && dow === "*") return `Elke ${h.slice(2)} uur op minuut ${Number(m)}`;
  if (at && dom === "*" && mon === "*" && dow === "*") return `Elke dag ${at}`;
  if (at && dom === "*" && mon === "*" && /^[0-7a-z,-]+$/i.test(dow)) {
    const days = [...(parseCron(text)!.dow)].sort((a, b) => ((a + 6) % 7) - ((b + 6) % 7)).map(day => DAY_NAMES[day]);
    if (days.join() === "maandag,dinsdag,woensdag,donderdag,vrijdag") return `Elke werkdag ${at}`;
    return `Elke ${days.join(", ")} ${at}`;
  }
  if (at && single(dom) && mon === "*" && dow === "*") return `Op dag ${Number(dom)} van elke maand ${at}`;
  return `Volgens cronschema ${text}`;
}

/**
 * A run is missed when the job is enabled, the most recent scheduled time (with 5 minutes grace) lies after the
 * job was created, and no run started at or after that time. Times in seconds since the epoch.
 */
export function isMissed(expression: string, enabled: boolean, createdAt: number, lastStart: number | null | undefined, now: number): boolean {
  if (!enabled) return false;
  const due = previousRun(expression, new Date((now - 300) * 1000));
  if (!due) return false;
  const dueSeconds = due.getTime() / 1000;
  if (dueSeconds <= createdAt) return false;
  return lastStart == null || lastStart < dueSeconds - 60;
}

export type Picker =
  | { mode: "minutes"; every: number }
  | { mode: "hourly"; minute: number }
  | { mode: "daily"; time: string }
  | { mode: "weekly"; days: number[]; time: string }
  | { mode: "monthly"; day: number; time: string }
  | { mode: "advanced"; expression: string };

/** Schedule picker → cron expression; null when the input is incomplete or invalid. */
export function buildCron(picker: Picker): string | null {
  const time = (value: string) => { const match = /^(\d{1,2}):(\d{2})$/.exec(value); if (!match) return null; const [h, m] = [Number(match[1]), Number(match[2])]; return h <= 23 && m <= 59 ? { h, m } : null; };
  let expression: string | null = null;
  if (picker.mode === "minutes" && Number.isInteger(picker.every) && picker.every >= 1 && picker.every <= 59) expression = picker.every === 1 ? "* * * * *" : `*/${picker.every} * * * *`;
  if (picker.mode === "hourly" && Number.isInteger(picker.minute) && picker.minute >= 0 && picker.minute <= 59) expression = `${picker.minute} * * * *`;
  if (picker.mode === "daily") { const t = time(picker.time); if (t) expression = `${t.m} ${t.h} * * *`; }
  if (picker.mode === "weekly") { const t = time(picker.time); const days = [...new Set(picker.days)].filter(day => Number.isInteger(day) && day >= 0 && day <= 6).sort(); if (t && days.length) expression = `${t.m} ${t.h} * * ${days.join(",")}`; }
  if (picker.mode === "monthly") { const t = time(picker.time); if (t && Number.isInteger(picker.day) && picker.day >= 1 && picker.day <= 28) expression = `${t.m} ${t.h} ${picker.day} * *`; }
  if (picker.mode === "advanced") expression = picker.expression.trim().replace(/\s+/g, " ");
  return expression && parseCron(expression) ? expression : null;
}

/** Best guess of picker settings for an existing expression (falls back to advanced). */
export function pickerFor(expression: string): Picker {
  const text = expression.trim();
  let match: RegExpExecArray | null;
  if (text === "* * * * *") return { mode: "minutes", every: 1 };
  if ((match = /^\*\/(\d+) \* \* \* \*$/.exec(text))) return { mode: "minutes", every: Number(match[1]) };
  if ((match = /^(\d+) \* \* \* \*$/.exec(text))) return { mode: "hourly", minute: Number(match[1]) };
  if ((match = /^(\d+) (\d+) \* \* \*$/.exec(text))) return { mode: "daily", time: `${pad(Number(match[2]))}:${pad(Number(match[1]))}` };
  if ((match = /^(\d+) (\d+) \* \* ([0-6](,[0-6])*)$/.exec(text))) return { mode: "weekly", days: match[3].split(",").map(Number), time: `${pad(Number(match[2]))}:${pad(Number(match[1]))}` };
  if ((match = /^(\d+) (\d+) (\d+) \* \*$/.exec(text)) && Number(match[3]) <= 28) return { mode: "monthly", day: Number(match[3]), time: `${pad(Number(match[2]))}:${pad(Number(match[1]))}` };
  return { mode: "advanced", expression: text };
}

export const DAY_LABELS = DAY_NAMES;
