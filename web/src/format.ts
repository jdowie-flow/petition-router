import type { Estimate } from "./api";

export const percent = (share: number) => `${Math.round(share * 100)}%`;

/** Percentage points: "+12", "0" or "−3". */
const signed = (share: number) => {
  const points = Math.round(share * 100);
  return points > 0 ? `+${points}` : points < 0 ? `−${-points}` : "0";
};

export const interval = ([, low, high]: Estimate) => `${percent(low)} to ${percent(high)}`;

/** ["+12 points", "+5 to +19"] */
export const difference = ([value, low, high]: Estimate) => [
  `${signed(value)} points`,
  `${signed(low)} to ${signed(high)}`,
];

export const dollars = (amount: number | null) =>
  amount === null ? "Unknown" : `$${amount.toFixed(2)}`;

export function duration(seconds: number | null) {
  if (seconds === null) return "";
  if (seconds < 0.001) return "under 1 ms";
  return seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(1)} s`;
}

/** Whether a difference is clear: its whole 95% interval is above zero, or below it. */
export function verdict([, low, high]: Estimate) {
  if (low > 0) return "ahead";
  if (high < 0) return "behind";
  return "unclear";
}

/** "anthropic/claude-haiku-5-5" -> "Claude Haiku 5.5". Other models keep their own name. */
export function routerName(name: string) {
  if (name === "tfidf") return "Word matching (TF-IDF)";
  const model = name.split("/").pop() ?? name;
  const claude = /^claude-([a-z]+)-(\d+)-(\d+)$/.exec(model);
  if (!claude) return model;
  const [, family, major, minor] = claude;
  return `Claude ${family[0].toUpperCase()}${family.slice(1)} ${major}.${minor}`;
}
