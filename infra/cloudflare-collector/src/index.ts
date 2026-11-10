interface Env {
  RAW_BUCKET: R2Bucket;
  NTPC_PAGE_SIZE: string;
  COLLECTION_END_AT: string;
  MAX_OBJECT_BYTES: string;
  COLLECT_TOKEN?: string;
}

const TAIPEI_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json";
const NTPC_URL = "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json";
const WEATHER_URL = "https://api.open-meteo.com/v1/forecast";
const COST_GUARD_KEY = "control/cost-guard.json";
const MAX_PROJECT_WRITES = 10_000;
const MAX_PROJECT_RESERVED_BYTES = 8_000_000_000;
const RESERVED_WRITES_PER_RUN = 5;
const RESERVED_BYTES_PER_RUN = 4_000_000;
const WARNING_RATIO = 0.8;

export default {
  async scheduled(_controller: ScheduledController, env: Env, context: ExecutionContext) {
    context.waitUntil(runCollection(env));
  },
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      const now = new Date();
      const collectionEnd = collectionEndFromEnv(env);
      return Response.json({
        status: "ok",
        service: "youbike-collector",
        collection_active: now < collectionEnd,
        collection_end_at: collectionEnd.toISOString(),
        max_object_bytes: maxObjectBytesFromEnv(env),
        cost_guardrail: "scheduled collection stops before fetching or writing after collection_end_at",
        cost_guard: {
          maximum_writes: MAX_PROJECT_WRITES,
          maximum_reserved_bytes: MAX_PROJECT_RESERVED_BYTES,
          warning_ratio: WARNING_RATIO,
          state_visibility: "internal R2 control object and Worker logs",
        },
      });
    }
    if (url.pathname === "/collect" && request.method === "POST") {
      if (!env.COLLECT_TOKEN) return new Response("Not found", { status: 404 });
      if (request.headers.get("authorization") !== `Bearer ${env.COLLECT_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 });
      }
      await runCollection(env);
      return Response.json({ status: "completed" });
    }
    return new Response("Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;

async function runCollection(env: Env): Promise<void> {
  const fetchedAt = new Date();
  const collectionEnd = collectionEndFromEnv(env);
  if (fetchedAt >= collectionEnd) return;
  if (!(await reserveCostBudget(env, fetchedAt))) return;
  const jobs: Array<Promise<CollectionRecord>> = [
    collectAndStore(env, "taipei", fetchedAt, fetchJson(TAIPEI_URL)),
    collectAndStore(env, "new_taipei", fetchedAt, fetchNewTaipei(Number(env.NTPC_PAGE_SIZE || 1000))),
  ];
  if (fetchedAt.getUTCMinutes() < 5) {
    jobs.push(collectAndStore(env, "weather_forecast", fetchedAt, fetchWeather(fetchedAt)));
  }
  const outcomes = await Promise.allSettled(jobs);
  const manifest = {
    fetched_at: fetchedAt.toISOString(),
    duration_basis: "scheduled-trigger",
    outcomes: outcomes.map((outcome) =>
      outcome.status === "fulfilled"
        ? { status: "success", ...outcome.value }
        : { status: "failure", error: safeError(outcome.reason) },
    ),
  };
  const manifestKey = `manifests/date=${datePart(fetchedAt)}/${compactTimestamp(fetchedAt)}.json`;
  const manifestBody = new TextEncoder().encode(JSON.stringify(manifest));
  if (manifestBody.byteLength > maxObjectBytesFromEnv(env)) {
    throw new Error(`Manifest exceeded MAX_OBJECT_BYTES (${manifestBody.byteLength} bytes)`);
  }
  await env.RAW_BUCKET.put(manifestKey, manifestBody, {
    httpMetadata: { contentType: "application/json" },
  });
  if (outcomes.some((outcome) => outcome.status === "rejected")) {
    throw new Error(`Collection partially failed; inspect ${manifestKey}`);
  }
}

type CollectionRecord = { source: string; object_key: string; records: number; sha256: string };

async function collectAndStore(
  env: Env,
  source: string,
  fetchedAt: Date,
  pendingPayload: Promise<unknown>,
): Promise<CollectionRecord> {
  const payload = await pendingPayload;
  if (!Array.isArray(payload) && typeof payload !== "object") throw new Error(`${source} returned invalid JSON`);
  const body = new TextEncoder().encode(JSON.stringify(payload)).buffer as ArrayBuffer;
  const maximumBytes = maxObjectBytesFromEnv(env);
  if (body.byteLength > maximumBytes) {
    throw new Error(`${source} exceeded MAX_OBJECT_BYTES (${body.byteLength} > ${maximumBytes})`);
  }
  const checksum = await sha256(body);
  const key = `source=${source}/date=${datePart(fetchedAt)}/hour=${String(fetchedAt.getUTCHours()).padStart(2, "0")}/${compactTimestamp(fetchedAt)}-${checksum.slice(0, 12)}.json.gz`;
  const compressedBody = await new Response(gzip(body)).arrayBuffer();
  await env.RAW_BUCKET.put(key, compressedBody, {
    httpMetadata: { contentType: "application/json", contentEncoding: "gzip" },
    customMetadata: { sha256: checksum, fetched_at: fetchedAt.toISOString() },
  });
  const records = Array.isArray(payload) ? payload.length : 1;
  return { source, object_key: key, records, sha256: checksum };
}

async function fetchNewTaipei(pageSize: number): Promise<unknown[]> {
  const records: unknown[] = [];
  for (let page = 0; page <= 20; page += 1) {
    const batch = await fetchJson(`${NTPC_URL}?page=${page}&size=${pageSize}`);
    if (!Array.isArray(batch)) throw new Error(`New Taipei page ${page} is not an array`);
    records.push(...batch);
    if (batch.length < pageSize) return records;
  }
  throw new Error("New Taipei pagination exceeded safety limit");
}

async function fetchWeather(issuedAt: Date): Promise<object> {
  const params = new URLSearchParams({
    latitude: "25.0375,25.1000,24.9900",
    longitude: "121.5637,121.5000,121.7000",
    hourly: "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,precipitation_probability,weather_code,wind_speed_10m,wind_gusts_10m",
    forecast_hours: "48",
    timezone: "Asia/Taipei",
  });
  return { issued_at: issuedAt.toISOString(), locations: await fetchJson(`${WEATHER_URL}?${params}`) };
}

async function fetchJson(url: string, attempts = 4): Promise<unknown> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, { headers: { "user-agent": "greater-taipei-youbike-forecast/0.1" } });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      if (attempt + 1 < attempts) await delay(2 ** attempt * 500 + Math.random() * 300);
    }
  }
  throw lastError;
}

function gzip(body: ArrayBuffer): ReadableStream {
  const stream = new Blob([body]).stream();
  return stream.pipeThrough(new CompressionStream("gzip"));
}

async function sha256(body: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", body);
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

const delay = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const datePart = (date: Date) => date.toISOString().slice(0, 10);
const compactTimestamp = (date: Date) => date.toISOString().replace(/[-:]/g, "").replace(".000", "");
const safeError = (error: unknown) => error instanceof Error ? error.message : String(error);

function collectionEndFromEnv(env: Env): Date {
  const value = new Date(env.COLLECTION_END_AT);
  if (!env.COLLECTION_END_AT || Number.isNaN(value.getTime())) {
    throw new Error("COLLECTION_END_AT must be a valid ISO 8601 timestamp");
  }
  return value;
}

function maxObjectBytesFromEnv(env: Env): number {
  const value = Number(env.MAX_OBJECT_BYTES);
  if (!Number.isInteger(value) || value <= 0 || value > 1_000_000) {
    throw new Error("MAX_OBJECT_BYTES must be an integer from 1 to 1000000");
  }
  return value;
}

type CostGuard = {
  reserved_writes: number;
  reserved_bytes: number;
  maximum_writes: number;
  maximum_reserved_bytes: number;
  warning: boolean;
  stopped: boolean;
  updated_at: string | null;
};

const emptyCostGuard = (): CostGuard => ({
  reserved_writes: 0,
  reserved_bytes: 0,
  maximum_writes: MAX_PROJECT_WRITES,
  maximum_reserved_bytes: MAX_PROJECT_RESERVED_BYTES,
  warning: false,
  stopped: false,
  updated_at: null,
});

async function readCostGuard(env: Env): Promise<CostGuard> {
  const object = await env.RAW_BUCKET.get(COST_GUARD_KEY);
  if (!object) return emptyCostGuard();
  try {
    return { ...emptyCostGuard(), ...await object.json<Partial<CostGuard>>() };
  } catch {
    throw new Error("Cost guard state is malformed; collection stopped safely");
  }
}

async function reserveCostBudget(env: Env, fetchedAt: Date): Promise<boolean> {
  const current = await readCostGuard(env);
  if (current.stopped) return false;
  const projectedWrites = current.reserved_writes + RESERVED_WRITES_PER_RUN;
  const projectedBytes = current.reserved_bytes + RESERVED_BYTES_PER_RUN;
  const stopped = projectedWrites > MAX_PROJECT_WRITES || projectedBytes > MAX_PROJECT_RESERVED_BYTES;
  const warning =
    projectedWrites >= MAX_PROJECT_WRITES * WARNING_RATIO ||
    projectedBytes >= MAX_PROJECT_RESERVED_BYTES * WARNING_RATIO;
  const next: CostGuard = {
    reserved_writes: projectedWrites,
    reserved_bytes: projectedBytes,
    maximum_writes: MAX_PROJECT_WRITES,
    maximum_reserved_bytes: MAX_PROJECT_RESERVED_BYTES,
    warning,
    stopped,
    updated_at: fetchedAt.toISOString(),
  };
  await env.RAW_BUCKET.put(COST_GUARD_KEY, JSON.stringify(next), {
    httpMetadata: { contentType: "application/json" },
  });
  if (stopped) {
    console.error("COST_GUARD_STOP: project write or storage reservation limit reached");
    return false;
  }
  if (warning) console.warn("COST_GUARD_WARNING: project usage reservation reached 80% of limit");
  return true;
}
