import type { CutoffRouter, Estimate, Summary } from "./api";
import { list, routerName, verdict } from "./format";

type Checked = CutoffRouter & { extra_lead: Estimate };

/**
 * Whether any model seems to be remembering answers: doing clearly better, against word
 * matching, on petitions answered before its training cutoff than after. Null when no model
 * can be checked.
 */
export function remembering({ training_cutoffs }: Summary): string | null {
  const checked = training_cutoffs.groups
    .flatMap((group) => group.routers)
    .filter((router): router is Checked => router.extra_lead !== undefined);
  if (checked.length === 0) return null;

  const ahead = checked.filter((router) => verdict(router.extra_lead) === "ahead");
  if (ahead.length === 0) {
    const who =
      checked.length === 1
        ? routerName(checked[0].name)
        : checked.length === 2
          ? "either model"
          : "any of the models";
    return `There is no clear sign that ${who} is remembering answers.`;
  }
  const names = list(ahead.map((router) => routerName(router.name)));
  return ahead.length === 1
    ? `${names} does clearly better, against word matching, on petitions answered before its cutoff, so it may be remembering answers.`
    : `${names} do clearly better, against word matching, on petitions answered before their cutoffs, so they may be remembering answers.`;
}
