interface Env {
  RAW_BUCKET: R2Bucket;
  NTPC_PAGE_SIZE: string;
  COLLECTION_START_AT: string;
  COLLECTION_END_AT: string;
  MAX_OBJECT_BYTES: string;
  COLLECT_TOKEN?: string;
}

const TAIPEI_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json";
const NTPC_URL = "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json";
const WEATHER_URL = "https://api.open-meteo.com/v1/forecast";
const COST_GUARD_KEY = "control/cost-guard.json";
const QUALITY_KEY = "control/collection-quality.json";
const SOURCE_NAMES = ["taipei", "new_taipei", "weather_forecast"] as const;
const MAX_PROJECT_WRITES = 10_000;
const MAX_PROJECT_RESERVED_BYTES = 8_000_000_000;
const RESERVED_WRITES_PER_RUN = 6;
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
  const quality = await readOrRebuildQuality(env, fetchedAt);
  const jobs: CollectionJob[] = [
    { source: "taipei", pending: collectAndStore(env, "taipei", fetchedAt, fetchJson(TAIPEI_URL)) },
    {
      source: "new_taipei",
      pending: collectAndStore(
        env,
        "new_taipei",
        fetchedAt,
        fetchNewTaipei(Number(env.NTPC_PAGE_SIZE || 1000)),
      ),
    },
  ];
  if (fetchedAt.getUTCMinutes() < 5) {
    jobs.push({
      source: "weather_forecast",
      pending: collectAndStore(env, "weather_forecast", fetchedAt, fetchWeather(fetchedAt)),
    });
  }
  const settled = await Promise.allSettled(jobs.map((job) => job.pending));
  const outcomes: CollectionOutcome[] = settled.map((outcome, index) =>
    outcome.status === "fulfilled"
      ? { status: "success", ...outcome.value }
      : { status: "failure", source: jobs[index].source, error: safeError(outcome.reason) },
  );
  const manifest = {
    fetched_at: fetchedAt.toISOString(),
    duration_basis: "scheduled-trigger",
    outcomes,
  };
  const manifestKey = `manifests/date=${datePart(fetchedAt)}/${compactTimestamp(fetchedAt)}.json`;
  const manifestBody = new TextEncoder().encode(JSON.stringify(manifest));
  if (manifestBody.byteLength > maxObjectBytesFromEnv(env)) {
    throw new Error(`Manifest exceeded MAX_OBJECT_BYTES (${manifestBody.byteLength} bytes)`);
  }
  await env.RAW_BUCKET.put(manifestKey, manifestBody, {
    httpMetadata: { contentType: "application/json" },
  });
  await writeQuality(env, applyOutcomes(quality, fetchedAt, outcomes));
  if (outcomes.some((outcome) => outcome.status === "failure")) {
    throw new Error(`Collection partially failed; inspect ${manifestKey}`);
  }
}

type CollectionRecord = { source: SourceName; object_key: string; records: number; sha256: string };
type CollectionJob = { source: SourceName; pending: Promise<CollectionRecord> };
type CollectionOutcome =
  | ({ status: "success" } & CollectionRecord)
  | { status: "failure"; source: SourceName; error: string };
type SourceName = (typeof SOURCE_NAMES)[number];

async function collectAndStore(
  env: Env,
  source: SourceName,
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

function collectionStartFromEnv(env: Env): Date {
  const value = new Date(env.COLLECTION_START_AT);
  if (!env.COLLECTION_START_AT || Number.isNaN(value.getTime())) {
    throw new Error("COLLECTION_START_AT must be a valid ISO 8601 timestamp");
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

type SourceQuality = {
  objects: number;
  successes_since_tracking: number;
  failures_since_tracking: number;
  first_fetched_at: string | null;
  last_fetched_at: string | null;
  last_records: number | null;
  expected_objects: number;
  completeness: number;
};

type CollectionQuality = {
  official_start_at: string;
  initialized_at: string;
  updated_at: string;
  reconstruction_basis: string;
  historical_manifests: number;
  tracked_runs: number;
  complete_runs_since_tracking: number;
  partial_failure_runs_since_tracking: number;
  observed_hours: number;
  required_hours: number;
  five_days_met: boolean;
  minimum_station_completeness: number;
  minimum_required_completeness: number;
  collection_quality_met: boolean;
  sources: Record<SourceName, SourceQuality>;
};

async function readOrRebuildQuality(env: Env, at: Date): Promise<CollectionQuality> {
  const object = await env.RAW_BUCKET.get(QUALITY_KEY);
  if (object) {
    try {
      return await object.json<CollectionQuality>();
    } catch {
      throw new Error("Collection quality state is malformed; collection stopped safely");
    }
  }
  const start = collectionStartFromEnv(env);
  const sourceEntries = await Promise.all(
    SOURCE_NAMES.map(async (source) => [source, await reconstructSourceQuality(env, source, start, at)] as const),
  );
  const historicalManifests = await countObjects(env, "manifests/", start);
  return finalizeQuality(
    {
      official_start_at: start.toISOString(),
      initialized_at: at.toISOString(),
      updated_at: at.toISOString(),
      reconstruction_basis: "R2 immutable object keys; per-run manifests retained for failure audit",
      historical_manifests: historicalManifests,
      tracked_runs: 0,
      complete_runs_since_tracking: 0,
      partial_failure_runs_since_tracking: 0,
      observed_hours: 0,
      required_hours: 120,
      five_days_met: false,
      minimum_station_completeness: 0,
      minimum_required_completeness: 0.95,
      collection_quality_met: false,
      sources: Object.fromEntries(sourceEntries) as Record<SourceName, SourceQuality>,
    },
    at,
  );
}

async function reconstructSourceQuality(
  env: Env,
  source: SourceName,
  start: Date,
  at: Date,
): Promise<SourceQuality> {
  const timestamps: Date[] = [];
  let cursor: string | undefined;
  do {
    const page = await env.RAW_BUCKET.list({ prefix: `source=${source}/`, cursor, limit: 1000 });
    for (const object of page.objects) {
      const timestamp = timestampFromObjectKey(object.key);
      if (timestamp && timestamp >= start) timestamps.push(timestamp);
    }
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  timestamps.sort((left, right) => left.getTime() - right.getTime());
  return {
    objects: timestamps.length,
    successes_since_tracking: 0,
    failures_since_tracking: 0,
    first_fetched_at: timestamps[0]?.toISOString() ?? null,
    last_fetched_at: timestamps.at(-1)?.toISOString() ?? null,
    last_records: null,
    expected_objects: expectedObjects(source, start, at),
    completeness: 0,
  };
}

async function countObjects(env: Env, prefix: string, start: Date): Promise<number> {
  let count = 0;
  let cursor: string | undefined;
  do {
    const page = await env.RAW_BUCKET.list({ prefix, cursor, limit: 1000 });
    count += page.objects.filter((object) => {
      const timestamp = timestampFromObjectKey(object.key);
      return timestamp !== null && timestamp >= start;
    }).length;
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  return count;
}

function applyOutcomes(
  quality: CollectionQuality,
  fetchedAt: Date,
  outcomes: CollectionOutcome[],
): CollectionQuality {
  const start = new Date(quality.official_start_at);
  const complete = outcomes.every((outcome) => outcome.status === "success");
  quality.tracked_runs += 1;
  if (complete) quality.complete_runs_since_tracking += 1;
  else quality.partial_failure_runs_since_tracking += 1;
  for (const outcome of outcomes) {
    const source = quality.sources[outcome.source];
    if (outcome.status === "success") {
      source.objects += 1;
      source.successes_since_tracking += 1;
      source.first_fetched_at ??= fetchedAt.toISOString();
      source.last_fetched_at = fetchedAt.toISOString();
      source.last_records = outcome.records;
    } else {
      source.failures_since_tracking += 1;
    }
    source.expected_objects = expectedObjects(outcome.source, start, fetchedAt);
  }
  return finalizeQuality(quality, fetchedAt);
}

function finalizeQuality(quality: CollectionQuality, at: Date): CollectionQuality {
  const start = new Date(quality.official_start_at);
  quality.updated_at = at.toISOString();
  quality.observed_hours = round((at.getTime() - start.getTime()) / 3_600_000, 2);
  quality.five_days_met = quality.observed_hours >= quality.required_hours;
  for (const source of SOURCE_NAMES) {
    const summary = quality.sources[source];
    summary.expected_objects = expectedObjects(source, start, at);
    summary.completeness = summary.expected_objects
      ? round(Math.min(summary.objects / summary.expected_objects, 1), 4)
      : 0;
  }
  quality.minimum_station_completeness = Math.min(
    quality.sources.taipei.completeness,
    quality.sources.new_taipei.completeness,
  );
  quality.collection_quality_met =
    quality.five_days_met &&
    quality.minimum_station_completeness >= quality.minimum_required_completeness;
  return quality;
}

async function writeQuality(env: Env, quality: CollectionQuality): Promise<void> {
  await env.RAW_BUCKET.put(QUALITY_KEY, JSON.stringify(quality), {
    httpMetadata: { contentType: "application/json" },
  });
}

function expectedObjects(source: SourceName, start: Date, at: Date): number {
  const cadenceMilliseconds = source === "weather_forecast" ? 3_600_000 : 300_000;
  const firstExpected = Math.ceil(start.getTime() / cadenceMilliseconds) * cadenceMilliseconds;
  if (at.getTime() < firstExpected) return 0;
  return Math.floor((at.getTime() - firstExpected) / cadenceMilliseconds) + 1;
}

function timestampFromObjectKey(key: string): Date | null {
  const match = key.match(/(\d{8}T\d{6}(?:\.\d+)?Z)/);
  if (!match) return null;
  const compact = match[1];
  const normalized = `${compact.slice(0, 4)}-${compact.slice(4, 6)}-${compact.slice(6, 8)}T${compact.slice(9, 11)}:${compact.slice(11, 13)}:${compact.slice(13)}`;
  const value = new Date(normalized);
  return Number.isNaN(value.getTime()) ? null : value;
}

const round = (value: number, digits: number) => Number(value.toFixed(digits));
