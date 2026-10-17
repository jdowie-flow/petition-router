import { describe, expect, it } from "vitest";
import type { Petition } from "./api";
import { hashFor, indexFromHash, nextUnlabelled, reachable } from "./navigation";

const petitions: Petition[] = [1, 2, 3, 4, 5].map((id) => ({
  id,
  title: `Petition ${id}`,
  background: "",
  details: "",
}));
const labels = { 1: "HO", 2: "DfE", 3: "HO" }; // the first three are done

describe("petition addresses", () => {
  it("number petitions from 1, as people count", () => {
    expect(hashFor(36)).toBe("#label/37");
    expect(indexFromHash("#label/37")).toBe(36);
  });

  it("ignore any other address", () => {
    expect(indexFromHash("#label")).toBeNull();
    expect(indexFromHash("#results")).toBeNull();
    expect(indexFromHash("#label/abc")).toBeNull();
  });
});

describe("reachable", () => {
  it("shows any labelled petition again", () => {
    expect(reachable(1, petitions, labels)).toBe(1);
  });

  it("goes to where you left off when the address names no petition", () => {
    expect(reachable(null, petitions, labels)).toBe(3);
    expect(reachable(99, petitions, labels)).toBe(3);
  });

  it("never skips ahead of the first petition without a label", () => {
    expect(reachable(3, petitions, labels)).toBe(3);
    expect(reachable(4, petitions, labels)).toBe(3);
  });
});

describe("nextUnlabelled", () => {
  it("wraps round, and gives the total when every petition is labelled", () => {
    expect(nextUnlabelled(petitions, { 4: "HO", 5: "HO" }, 3)).toBe(0);
    const all = Object.fromEntries(petitions.map((p) => [p.id, "HO"]));
    expect(nextUnlabelled(petitions, all, 0)).toBe(5);
  });
});

describe("reachable once every petition is labelled", () => {
  const all = Object.fromEntries(petitions.map((p) => [p.id, "HO"]));

  it("shows any petition again", () => {
    expect(reachable(0, petitions, all)).toBe(0);
    expect(reachable(4, petitions, all)).toBe(4);
  });

  it("goes to the summary when the address names no petition", () => {
    expect(reachable(null, petitions, all)).toBe(petitions.length);
  });
});
