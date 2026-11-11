interface Env {
  ASSETS: Fetcher;
}

const TAIPEI_URL =
  "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json";
const NTPC_URL =
  "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json";
const COLLECTION_START_AT = "2026-11-10T07:51:49Z";
const REQUIRED_HOURS = 120;
const VERIFIED_QUALITY_AT = "2026-11-11T16:25:56.796Z";
const VERIFIED_HOURS = 32.57;
const VERIFIED_COMPLETENESS = 0.9719;
const VERIFIED_RUNS = 168;

type TaipeiRow = Record<string, string | number | null>;
type NewTaipeiRow = Record<string, string | number | null>;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({
        status: "ok",
        time: new Date().toISOString(),
        model: "collecting-training-data",
        service: "youbike-public-edge",
      });
    }

    if (request.method === "GET" && url.pathname === "/api/v1/stations/live") {
      try {
        return json(await liveStations(url.searchParams.get("source") ?? "all"), {
          "cache-control": "public, max-age=30, s-maxage=60",
        });
      } catch (error) {
        console.error("LIVE_STATIONS_ERROR", safeError(error));
        return json({ detail: "Official live feed unavailable" }, {}, 502);
      }
    }

    if (request.method === "GET" && url.pathname === "/api/v1/data/quality") {
      return json(publicQualityStatus(), {
        "cache-control": "public, max-age=60, s-maxage=300",
      });
    }

    if (url.pathname.startsWith("/api/") || url.pathname === "/health") {
      return json({ detail: "Not available until the formal model gate passes" }, {}, 503);
    }

    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;

async function liveStations(source: string) {
  if (!["all", "taipei", "new_taipei"].includes(source)) {
    throw new Error("Invalid source");
  }
  const [taipei, newTaipei] = await Promise.all([
    source === "all" || source === "taipei" ? fetchTaipei() : Promise.resolve([]),
    source === "all" || source === "new_taipei" ? fetchNewTaipei() : Promise.resolve([]),
  ]);
  const stations = [...taipei, ...newTaipei];
  return {
    as_of: new Date().toISOString(),
    count: stations.length,
    model_status: "collecting-training-data",
    stations,
  };
}

async function fetchTaipei() {
  const rows = await fetchJson<TaipeiRow[]>(TAIPEI_URL);
  if (!Array.isArray(rows)) throw new Error("Taipei response is not an array");
  return rows.map((row) => ({
    source: "taipei" as const,
    station_id: String(row.sno),
    station_name: String(row.sna ?? "").replace(/^YouBike2\.0_/, ""),
    district: String(row.sarea ?? ""),
    latitude: numeric(row.latitude),
    longitude: numeric(row.longitude),
    capacity: numeric(row.Quantity),
    available_bikes: numeric(row.available_rent_bikes),
    available_docks: numeric(row.available_return_bikes),
  }));
}

async function fetchNewTaipei() {
  const rows: NewTaipeiRow[] = [];
  for (let page = 0; page <= 20; page += 1) {
    const batch = await fetchJson<NewTaipeiRow[]>(`${NTPC_URL}?page=${page}&size=1000`);
    if (!Array.isArray(batch)) throw new Error(`New Taipei page ${page} is not an array`);
    rows.push(...batch);
    if (batch.length < 1000) break;
    if (page === 20) throw new Error("New Taipei pagination exceeded safety limit");
  }
  return rows.map((row) => ({
    source: "new_taipei" as const,
    station_id: String(row.sno),
    station_name: String(row.sna ?? "").replace(/^YouBike2\.0_/, ""),
    district: String(row.sarea ?? ""),
    latitude: numeric(row.lat),
    longitude: numeric(row.lng),
    capacity: numeric(row.tot_quantity),
    available_bikes: numeric(row.sbi_quantity),
    available_docks: numeric(row.bemp),
  }));
}

function publicQualityStatus() {
  return {
    generated_at: VERIFIED_QUALITY_AT,
    quality_basis:
      "Verified snapshot from the private R2 collection-quality control object; formal training re-syncs immutable evidence.",
    sources: {},
    scheduler_runs: { success: VERIFIED_RUNS, partial_failure: 0, failure: 0, malformed: 0 },
    minimum_requirement: {
      official_start_at: COLLECTION_START_AT,
      required_hours: REQUIRED_HOURS,
      observed_station_hours: VERIFIED_HOURS,
      minimum_completeness: 0.95,
      observed_station_completeness: VERIFIED_COMPLETENESS,
      five_days_met: VERIFIED_HOURS >= REQUIRED_HOURS,
      collection_quality_met: false,
    },
  };
}

async function fetchJson<T>(url: string, attempts = 3): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: { "user-agent": "greater-taipei-youbike-public-app/0.1" },
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return (await response.json()) as T;
    } catch (error) {
      lastError = error;
      if (attempt + 1 < attempts) await delay(250 * 2 ** attempt);
    }
  }
  throw lastError;
}

function numeric(value: string | number | null | undefined): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`Invalid numeric value: ${String(value)}`);
  return parsed;
}

function json(body: unknown, headers: Record<string, string> = {}, status = 200): Response {
  return Response.json(body, { status, headers });
}

function safeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
