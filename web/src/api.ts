// What the server in src/petition_router/server.py sends.

/** A share, with its 95% interval: [estimate, low, high]. */
export type Estimate = [number, number, number];

export interface Petition {
  id: number;
  title: string;
  background: string;
  details: string;
}

export interface Labelling {
  departments: Record<string, string>; // A to Z, as the model sees them
  petitions: Petition[];
  labels: Record<string, string>; // petition id -> department
  agreed: string | null; // when the rules on the first page were agreed to
  finished: string | null; // when the last label was saved; they're locked after that
}

export interface Router {
  name: string;
  petitions: number;
  accuracy: Estimate;
  vs_tfidf?: Estimate;
  unusable: number;
  cost_per_1000: number | null;
  median_seconds: number | null;
}

/** A router's accuracy on the petitions answered before and after a training cutoff. */
export interface CutoffRouter {
  name: string;
  before: Estimate | null;
  after: Estimate | null;
  extra_lead?: Estimate; // how much further ahead of word matching it is before than after
}

export interface CutoffGroup {
  cutoff: string; // the last month of the training data, such as "2026-06"
  before: number; // petitions answered by the end of that month
  after: number;
  routers: CutoffRouter[]; // the models with this cutoff, then word matching
}

export interface Mistake {
  id: number;
  title: string;
  departments: string[];
  reason: string;
  mine: string | null;
}

export interface Changes {
  petitions: number;
  changed: number;
}

export interface Summary {
  petitions: number;
  departments: Record<string, string>;
  most_common: { department: string; share: number } | null;
  routers: Router[];
  me: {
    petitions: number;
    accuracy: Estimate;
    median_seconds: number | null;
    routers: {
      name: string;
      petitions: number;
      accuracy: Estimate;
      vs_me: Estimate;
      agrees_with_me: number;
    }[];
  } | null;
  consistency: {
    name: string;
    repeated: Changes | null;
    reversed: Changes | null;
    reversed_accuracy: number | null;
    runs: number;
    petitions: number;
    stable: number;
    right_when_stable: number | null;
    right_otherwise: number | null;
  }[];
  by_department: { department: string; petitions: number; accuracy: Record<string, number> }[];
  training_cutoffs: {
    groups: CutoffGroup[];
    unknown: string[]; // models whose training cutoff isn't known
  };
  mixups: {
    router: string;
    pairs: { tagged: string; chose: string | null; petitions: Mistake[] }[];
  } | null;
}

export class ServerError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers: { "Content-Type": "application/json" } });
  } catch {
    throw new ServerError(
      "Cannot reach the server. If make has stopped, run it again in the terminal, then reload this page.",
      0,
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : "Something went wrong.";
    throw new ServerError(detail, response.status);
  }
  return body as T;
}

export const getLabelling = () => call<Labelling>("/api/labelling");

export const agree = () => call<{ agreed: string }>("/api/agreement", { method: "PUT" });

export const saveLabel = (petitionId: number, department: string, seconds: number) =>
  call<{ labelled: number; finished: string | null }>(`/api/labels/${petitionId}`, {
    method: "PUT",
    body: JSON.stringify({ department, seconds }),
  });

export const getResults = () => call<Summary>("/api/results");
