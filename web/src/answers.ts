import type { Estimate, Summary } from "./api";
import { difference, percent, routerName, verdict } from "./format";

export interface Answer {
  question: string;
  answer: string;
  detail: string;
}

const VERDICT = { ahead: "Yes", behind: "No", unclear: "Too close to call" };

/** What a difference's 95% interval says about it. */
function gap(estimate: Estimate) {
  const [, range] = difference(estimate);
  const clear = verdict(estimate) === "unclear" ? "could be down to chance" : "is clear";
  return `The difference ${clear}: its 95% interval is ${range} points.`;
}

/**
 * The questions the results page answers, each answered in a line, for the model that
 * did best against the tags.
 */
export function answers(summary: Summary): Answer[] {
  const { petitions, routers, me, departments, most_common: top } = summary;
  const best = routers.find((router) => router.name !== "tfidf");
  if (!best) return [];
  const model = routerName(best.name);
  const found = [
    {
      question: "How often does a model pick the right department?",
      answer: percent(best.accuracy[0]),
      detail:
        `${model}, across all ${petitions} petitions.` +
        (top
          ? ` For comparison, always answering ${departments[top.department] ?? top.department}` +
            ` (the most common department) would get ${percent(top.share)} right.`
          : ""),
    },
  ];

  const baseline = routers.find((router) => router.name === "tfidf");
  if (baseline && best.vs_tfidf) {
    found.push({
      question: "Is a model better than simple word matching?",
      answer: VERDICT[verdict(best.vs_tfidf)],
      detail:
        `${model} got ${percent(best.accuracy[0])} and word matching (TF-IDF) got ` +
        `${percent(baseline.accuracy[0])}. ${gap(best.vs_tfidf)}`,
    });
  }

  const versus = me?.routers.find((router) => router.name === best.name);
  if (me && versus) {
    found.push({
      question: "Is a model better than a person?",
      answer: VERDICT[verdict(versus.vs_me)],
      detail:
        `On the ${me.petitions} petitions you labelled, ${model} got ` +
        `${percent(versus.accuracy[0])} and you got ${percent(me.accuracy[0])}. ${gap(versus.vs_me)}`,
    });
  }
  return found;
}
