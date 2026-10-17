import type { Labelling, Petition } from "./api";

type Labels = Labelling["labels"];

/** The next petition without a label after `from`, wrapping round. The total if none are left. */
export function nextUnlabelled(petitions: Petition[], labels: Labels, from: number) {
  for (let step = 1; step <= petitions.length; step++) {
    const i = (from + step) % petitions.length;
    if (!(petitions[i].id in labels)) return i;
  }
  return petitions.length;
}

/** Each petition has its own address, so the browser's Back and Forward move between them. */
export const hashFor = (index: number) => `#label/${index + 1}`;

/** "#label/37" -> 36. Null for any other address. */
export function indexFromHash(hash: string) {
  const match = /^#label\/(\d+)$/.exec(hash);
  return match ? Number(match[1]) - 1 : null;
}

/**
 * Where a request to see petition `wanted` lands. Any labelled petition can be seen again,
 * but no one can skip ahead: the furthest is the first petition without a label.
 */
export function reachable(wanted: number | null, petitions: Petition[], labels: Labels) {
  const furthest = nextUnlabelled(petitions, labels, -1);
  if (wanted === null || wanted < 0 || wanted >= petitions.length) return furthest;
  return petitions[wanted].id in labels ? wanted : furthest;
}
