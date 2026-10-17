/**
 * Departments matching what's been typed, best first: acronyms that start with it,
 * then any acronym or name that contains it. So "ho" puts HO first, and "health"
 * finds DHSC.
 */
export function matchDepartments(typed: string, departments: Record<string, string>): string[] {
  const query = typed.trim().toLowerCase();
  const codes = Object.keys(departments);
  if (!query) return codes;
  const starts = codes.filter((code) => code.toLowerCase().startsWith(query));
  const contains = codes.filter(
    (code) =>
      !starts.includes(code) &&
      (code.toLowerCase().includes(query) || departments[code].toLowerCase().includes(query)),
  );
  return [...starts, ...contains];
}
