import { describe, expect, it } from "vitest";
import { routerName, verdict } from "./format";

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
