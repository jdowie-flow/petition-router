/** A department's acronym, with its full name on hover. */
export function Acronym({ code, name }: { code: string; name?: string }) {
  return (
    <abbr className="acronym" title={name}>
      {code}
    </abbr>
  );
}
