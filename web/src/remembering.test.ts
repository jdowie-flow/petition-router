import { describe, expect, it } from "vitest";
import type { CutoffRouter, Summary } from "./api";
import { remembering } from "./remembering";

const sonnet = "anthropic/claude-sonnet-5-5";
const haiku = "anthropic/claude-haiku-5-5";

const summary = (...routers: CutoffRouter[]) =>
  ({
    training_cutoffs: {
      groups: [{ cutoff: "2026-06", before: 325, after: 71, routers }],
      unknown: [],
    },
  }) as unknown as Summary;

const tfidf: CutoffRouter = { name: "tfidf", before: [0.4, 0.35, 0.46], after: [0.38, 0.27, 0.5] };

describe("remembering", () => {
  it("finds no clear sign when every range includes 0", () => {
    const models = [
      { name: sonnet, before: null, after: null, extra_lead: [-0.01, -0.14, 0.14] },
      { name: haiku, before: null, after: null, extra_lead: [0.01, -0.12, 0.15] },
    ] satisfies CutoffRouter[];
    expect(remembering(summary(...models, tfidf))).toBe(
      "There is no clear sign that either model is remembering answers.",
    );
    expect(remembering(summary(models[0], tfidf))).toBe(
      "There is no clear sign that Claude Sonnet 5.5 is remembering answers.",
    );
  });

  it("names a model that does clearly better before its cutoff", () => {
    const models = [
      { name: sonnet, before: null, after: null, extra_lead: [0.2, 0.08, 0.31] },
      { name: haiku, before: null, after: null, extra_lead: [0.01, -0.12, 0.15] },
    ] satisfies CutoffRouter[];
    expect(remembering(summary(...models, tfidf))).toBe(
      "Claude Sonnet 5.5 does clearly better, against word matching, on petitions answered before its cutoff, so it may be remembering answers.",
    );
  });

  it("has nothing to say when no model can be checked", () => {
    expect(remembering(summary(tfidf))).toBeNull();
  });
});
