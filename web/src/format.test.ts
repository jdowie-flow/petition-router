import { describe, expect, it } from "vitest";
import { difference, list, month, routerName, verdict } from "./format";

describe("difference", () => {
  it("gives a difference in points, with its range", () => {
    expect(difference([0.47, 0.42, 0.53])).toEqual(["+47 points", "+42 to +53"]);
    expect(difference([-0.008, -0.139, 0.138])).toEqual(["−1 point", "−14 to +14"]);
    expect(difference([0.001, -0.1, 0.1])).toEqual(["0 points", "−10 to +10"]);
  });
});

describe("month", () => {
  it("writes a year and month out in full", () => {
    expect(month("2026-06")).toBe("June 2026");
    expect(month("2025-12")).toBe("December 2025");
  });
});

describe("list", () => {
  it("joins names the way a sentence does", () => {
    expect(list([])).toBe("");
    expect(list(["A"])).toBe("A");
    expect(list(["A", "B"])).toBe("A and B");
    expect(list(["A", "B", "C"])).toBe("A, B and C");
  });
});

describe("verdict", () => {
  it("calls a difference clear only when its whole interval is on one side of zero", () => {
    expect(verdict([0.1, 0.05, 0.15])).toBe("ahead");
    expect(verdict([-0.1, -0.15, -0.05])).toBe("behind");
    expect(verdict([0.09, -0.02, 0.2])).toBe("unclear");
  });
});

describe("routerName", () => {
  it("writes Claude model names the way people do", () => {
    expect(routerName("anthropic/claude-sonnet-5-5")).toBe("Claude Sonnet 5.5");
    expect(routerName("tfidf")).toBe("Word matching (TF-IDF)");
  });

  it("leaves other models as they are", () => {
    expect(routerName("openai/gpt-5")).toBe("gpt-5");
  });
});
