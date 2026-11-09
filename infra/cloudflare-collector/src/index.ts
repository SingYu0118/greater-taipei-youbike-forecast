interface Env {
  RAW_BUCKET: R2Bucket;
  NTPC_PAGE_SIZE: string;
}

const TAIPEI_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json";
const NTPC_URL = "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json";
const WEATHER_URL = "https://api.open-meteo.com/v1/forecast";

export default {
  async scheduled(_controller: ScheduledController, env: Env, context: ExecutionContext) {
    context.waitUntil(runCollection(env));
  },
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return Response.json({ status: "ok", service: "youbike-collector" });
    }
    if (url.pathname === "/collect" && request.method === "POST") {
      await runCollection(env);
      return Response.json({ status: "completed" });
    }
    return new Response("Not found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;

async function runCollection(env: Env): Promise<void> {
  const fetchedAt = new Date();
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
  await env.RAW_BUCKET.put(manifestKey, JSON.stringify(manifest), {
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
  const checksum = await sha256(body);
  const key = `source=${source}/date=${datePart(fetchedAt)}/hour=${String(fetchedAt.getUTCHours()).padStart(2, "0")}/${compactTimestamp(fetchedAt)}-${checksum.slice(0, 12)}.json.gz`;
  await env.RAW_BUCKET.put(key, gzip(body), {
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
