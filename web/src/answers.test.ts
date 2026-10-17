import { describe, expect, it } from "vitest";
import { answers } from "./answers";
import type { Router, Summary } from "./api";

const router = (name: string, accuracy: Router["accuracy"], extra = {}): Router => ({
  name,
  petitions: 189,
  accuracy,
  unusable: 0,
  cost_per_1000: 0,
  median_seconds: 1.9,
  by_year: {},
  ...extra,
});

const summary: Summary = {
  petitions: 189,
  departments: { DfE: "Department for Education" },
  most_common: { department: "DfE", share: 0.1 },
  routers: [
    router("tfidf", [0.93, 0.89, 0.96]),
    router("anthropic/claude-sonnet-5-5", [0.9, 0.85, 0.94], { vs_tfidf: [-0.03, -0.09, 0.03] }),
  ],
  me: {
    petitions: 100,
    accuracy: [0.79, 0.7, 0.87],
    median_seconds: 24.1,
    routers: [
      {
        name: "anthropic/claude-sonnet-5-5",
        petitions: 100,
        accuracy: [0.95, 0.9, 0.99],
        vs_me: [0.16, 0.08, 0.25],
        agrees_with_me: 0.8,
      },
    ],
  },
  consistency: [],
  by_department: [],
  mixups: null,
};

describe("answers", () => {
  it("answers each question for the best model, saying when a gap could be chance", () => {
    const [accuracy, baseline, person] = answers(summary);
    expect(accuracy.answer).toBe("90%");
    expect(accuracy.detail).toContain("Claude Sonnet 5.5, across all 189 petitions");
    expect(accuracy.detail).toContain(
      "always answering Department for Education (the most common department) would get 10% right",
    );
    expect(baseline.question).toBe("Is a model better than simple word matching?");
    expect(baseline.answer).toBe("Too close to call");
    expect(baseline.detail).toContain("could be down to chance");
    expect(person.question).toBe("Is a model better than a person?");
    expect(person.answer).toBe("Yes");
    expect(person.detail).toContain("Claude Sonnet 5.5 got 95% and you got 79%");
  });

  it("has nothing to say before a model has run", () => {
    expect(answers({ ...summary, routers: [summary.routers[0]] })).toEqual([]);
  });
});
