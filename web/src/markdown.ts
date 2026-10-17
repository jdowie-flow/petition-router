import type { Estimate, Summary } from "./api";
import { difference, dollars, duration, interval, percent, routerName } from "./format";

/** A Markdown table. Columns marked true hold numbers, so they're aligned right. */
function table(columns: [string, boolean][], rows: string[][]) {
  const line = (cells: string[]) =>
    `| ${cells.map((cell) => cell.replaceAll("|", "\\|")).join(" | ")} |`;
  return [
    line(columns.map(([name]) => name)),
    `| ${columns.map(([, number]) => (number ? "---:" : "---")).join(" | ")} |`,
    ...rows.map(line),
  ].join("\n");
}

const compared = (estimate?: Estimate) => {
  if (!estimate) return "";
  const [points, range] = difference(estimate);
  return `${points} (${range})`;
};

/** The two main tables on the results page, as Markdown for a README. Numbers only. */
export function markdown({ petitions, routers, me }: Summary) {
  const parts = [
    `All ${petitions} petitions:`,
    table(
      [
        ["Routed by", false],
        ["Right department", true],
        ["95% interval", false],
        ["Compared with word matching", false],
        ["Unusable replies", true],
        ["Cost per 1,000", true],
        ["Median time", true],
      ],
      routers.map((router) => [
        routerName(router.name),
        percent(router.accuracy[0]),
        interval(router.accuracy),
        compared(router.vs_tfidf),
        String(router.unusable),
        dollars(router.cost_per_1000),
        duration(router.median_seconds),
      ]),
    ),
  ];
  if (me) {
    parts.push(
      `The ${me.petitions} petitions I labelled:`,
      table(
        [
          ["Routed by", false],
          ["Right department", true],
          ["95% interval", false],
          ["Compared with me", false],
          ["Same answer as me", true],
        ],
        [
          ["Me", percent(me.accuracy[0]), interval(me.accuracy), "", ""],
          ...me.routers.map((router) => [
            routerName(router.name),
            percent(router.accuracy[0]),
            interval(router.accuracy),
            compared(router.vs_me),
            percent(router.agrees_with_me),
          ]),
        ],
      ),
    );
  }
  return `${parts.join("\n\n")}\n`;
}
