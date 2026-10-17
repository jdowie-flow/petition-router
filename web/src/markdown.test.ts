import { describe, expect, it } from "vitest";
import type { Summary } from "./api";
import { markdown } from "./markdown";

const haiku = "anthropic/claude-haiku-5-5";

const summary: Summary = {
  petitions: 812,
  departments: {},
  most_common: null,
  routers: [
    {
      name: haiku,
      petitions: 812,
      accuracy: [0.74, 0.71, 0.77],
      vs_tfidf: [0.12, 0.08, 0.16],
      unusable: 2,
      cost_per_1000: 0.07,
      median_seconds: 1.9,
      by_year: {},
    },
    {
      name: "tfidf",
      petitions: 812,
      accuracy: [0.62, 0.59, 0.65],
      unusable: 0,
      cost_per_1000: 0,
      median_seconds: 0.0004,
      by_year: {},
    },
  ],
  me: {
    petitions: 100,
    accuracy: [0.8, 0.72, 0.87],
    median_seconds: 21,
    routers: [
      {
        name: haiku,
        petitions: 100,
        accuracy: [0.76, 0.68, 0.84],
        vs_me: [-0.04, -0.12, 0.04],
        agrees_with_me: 0.81,
      },
    ],
  },
  consistency: [],
  by_department: [],
  mixups: null,
};

describe("markdown", () => {
  it("writes the two main tables, right-aligning the numbers", () => {
    const lines = markdown(summary).split("\n");
    expect(lines).toContain("All 812 petitions:");
    expect(lines).toContain("| --- | ---: | --- | --- | ---: | ---: | ---: |");
    expect(lines).toContain(
      "| Claude Haiku 5.5 | 74% | 71% to 77% | +12 points (+8 to +16) | 2 | $0.07 | 1.9 s |",
    );
    expect(lines).toContain(
      "| Word matching (TF-IDF) | 62% | 59% to 65% |  | 0 | $0.00 | under 1 ms |",
    );
    expect(lines).toContain("The 100 petitions I labelled:");
    expect(lines).toContain("| Me | 80% | 72% to 87% |  |  |");
    expect(lines).toContain(
      "| Claude Haiku 5.5 | 76% | 68% to 84% | −4 points (−12 to +4) | 81% |",
    );
  });

  it("leaves out the second table until there are labels to compare with", () => {
    expect(markdown({ ...summary, me: null })).not.toContain("I labelled");
  });
});
