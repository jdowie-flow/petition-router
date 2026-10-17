import { describe, expect, it } from "vitest";
import { matchDepartments } from "./departments";

const departments = {
  DCMS: "Department for Culture, Media and Sport",
  DfE: "Department for Education",
  DHSC: "Department of Health and Social Care",
  HO: "Home Office",
  MoJ: "Ministry of Justice",
};

describe("matchDepartments", () => {
  it("keeps every department, in order, before anything is typed", () => {
    expect(matchDepartments("  ", departments)).toEqual(Object.keys(departments));
  });

  it("puts acronyms that start with the text first, ignoring case", () => {
    expect(matchDepartments("ho", departments)[0]).toBe("HO");
    expect(matchDepartments("dfe", departments)).toEqual(["DfE"]);
  });

  it("finds departments by any part of their name", () => {
    expect(matchDepartments("health", departments)).toEqual(["DHSC"]);
    expect(matchDepartments("justice", departments)).toEqual(["MoJ"]);
  });

  it("finds nothing for text that matches no department", () => {
    expect(matchDepartments("NHS England", departments)).toEqual([]);
  });
});
