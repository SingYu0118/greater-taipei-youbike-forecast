interface Env {
  ASSETS: Fetcher;
  RAW_BUCKET: R2Bucket;
}

const TAIPEI_URL =
  "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json";
const NTPC_URL =
  "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json";
const COLLECTION_START_AT = "2026-11-10T07:51:49Z";
const REQUIRED_HOURS = 120;
const QUALITY_OBJECT_KEY = "control/collection-quality.json";
const FORECAST_OBJECT_KEY = "control/latest-forecasts.json";

const MODEL_METRICS = {
  created_at: "2026-11-15T15:05:27.776112+00:00",
  model_id: "catboost-20261115T150527Z",
  code_version: "d2ce8c27f02cc59a128d824b93bffd2d26a4254e",
  winner: "catboost",
  selection_rule: "lowest mean CV MAE, then mean CV RMSE",
  validation: {
    folds: 3,
    validation_hours: 12,
    purge_minutes: 60,
    final_holdout_hours: 24,
  },
  coverage: {
    start: "2026-11-10T08:50:56.406000+00:00",
    end: "2026-11-15T08:10:56.950000+00:00",
    rows: 4858440,
    stations: 3401,
    final_holdout_rows: 976209,
  },
  cross_validation: {
    ridge: { mae: 2.9375401353, rmse: 4.5810315295 },
    random_forest: { mae: 2.7688278113, rmse: 4.3167240826 },
    extra_trees: { mae: 2.7530467549, rmse: 4.3106946822 },
    hist_gradient_boosting: { mae: 2.6414878037, rmse: 4.4175337109 },
    lightgbm: { mae: 2.6279362008, rmse: 4.3893793 },
    xgboost: { mae: 2.6109037578, rmse: 4.2696084713 },
    catboost: { mae: 2.6092097693, rmse: 4.3573270446 },
  },
  final_holdout: {
    catboost: {
      mae: 2.0258248485,
      rmse: 3.5003512183,
      wape: 0.1823992806,
      empty_recall: 0.352396892,
      full_recall: 0.2066352252,
    },
    baseline_persistence: {
      mae: 2.0562471766,
      rmse: 3.7006269989,
      wape: 0.1851384171,
      empty_recall: 0.627553852,
      full_recall: 0.5383639616,
    },
  },
  publication_gate: { beats_persistence_mae: true, passed: true },
  serving_status: "published-r2-forecast-snapshot",
} as const;

const MODEL_DRIVERS = {
  model: "catboost",
  sample_rows: 200,
  global_shap: [
    { feature: "available_bikes", mean_absolute_shap: 5.0077814948 },
    { feature: "neighbor_bike_ratio_mean", mean_absolute_shap: 0.6436324846 },
    { feature: "bikes_lag_5m", mean_absolute_shap: 0.3765229658 },
    { feature: "capacity", mean_absolute_shap: 0.2698631492 },
    { feature: "bikes_lag_15m", mean_absolute_shap: 0.198295144 },
    { feature: "bikes_rolling_std_60m", mean_absolute_shap: 0.1846700832 },
    { feature: "hour_sin", mean_absolute_shap: 0.1644985443 },
    { feature: "bikes_rolling_mean_60m", mean_absolute_shap: 0.1592443353 },
    { feature: "available_docks", mean_absolute_shap: 0.136350304 },
    { feature: "nearest_mrt_distance_m", mean_absolute_shap: 0.0933933147 },
  ],
  permutation_importance: [],
  caution: "SHAP values explain model behaviour, not causality. Risk recall remains below persistence and needs threshold-specific optimization.",
} as const;

type TaipeiRow = Record<string, string | number | null>;
type NewTaipeiRow = Record<string, string | number | null>;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({
        status: "ok",
        time: new Date().toISOString(),
        model: "ready",
        forecast_serving: "snapshot",
        service: "youbike-public-edge",
      });
    }

    if (request.method === "GET" && url.pathname === "/api/v1/forecasts/latest") {
      try {
        return json(await publicForecastSnapshot(env), {
          "cache-control": "public, max-age=30, s-maxage=60",
        });
      } catch (error) {
        console.error("FORECAST_SNAPSHOT_ERROR", safeError(error));
        return json({ detail: "Published forecast snapshot unavailable" }, {}, 503);
      }
    }

    const whatIfMatch = url.pathname.match(/^\/api\/v1\/stations\/([^/]+)\/what-if$/);
    if (request.method === "POST" && whatIfMatch) {
      try {
        return json(await publicWhatIf(request, env, decodeURIComponent(whatIfMatch[1])));
      } catch (error) {
        console.error("FORECAST_WHAT_IF_ERROR", safeError(error));
        return json({ detail: safeError(error) }, {}, 422);
      }
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
      return json(await publicQualityStatus(env), {
        "cache-control": "public, max-age=60, s-maxage=300",
      });
    }

    if (request.method === "GET" && url.pathname === "/api/v1/model/metrics") {
      return json(MODEL_METRICS, { "cache-control": "public, max-age=300, s-maxage=3600" });
    }

    if (request.method === "GET" && url.pathname === "/api/v1/model/drivers") {
      return json(MODEL_DRIVERS, { "cache-control": "public, max-age=300, s-maxage=3600" });
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
    model_status: "validated-results-ready",
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
    station_name_en: String(row.snaen ?? "").replace(/^YouBike2\.0_/, ""),
    district: String(row.sarea ?? ""),
    district_en: String(row.sareaen ?? ""),
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
    station_name_en: String(row.snaen ?? "").replace(/^YouBike2\.0_/, ""),
    district: String(row.sarea ?? ""),
    district_en: String(row.sareaen ?? ""),
    latitude: numeric(row.lat),
    longitude: numeric(row.lng),
    capacity: numeric(row.tot_quantity),
    available_bikes: numeric(row.sbi_quantity),
    available_docks: numeric(row.bemp),
  }));
}

type CollectionQuality = {
  official_start_at: string;
  updated_at: string;
  tracked_runs: number;
  complete_runs_since_tracking: number;
  partial_failure_runs_since_tracking: number;
  observed_hours: number;
  required_hours: number;
  five_days_met: boolean;
  minimum_station_completeness: number;
  minimum_required_completeness: number;
  collection_quality_met: boolean;
};

type ForecastStation = {
  source: "taipei" | "new_taipei";
  station_id: string;
  station_name_en?: string;
  district_en?: string;
  predicted_bikes: number;
  dry_prediction: number;
  heavy_rain_prediction: number;
};

type ForecastSnapshot = {
  schema_version: number;
  generated_at: string;
  as_of: string;
  count: number;
  model_status: "ready";
  serving_mode: "r2-batch-snapshot";
  model: { model_id: string; model_name: string };
  stations: ForecastStation[];
};

async function publicForecastSnapshot(env: Env): Promise<ForecastSnapshot> {
  const object = await env.RAW_BUCKET.get(FORECAST_OBJECT_KEY);
  if (!object) throw new Error(`Missing R2 forecast object: ${FORECAST_OBJECT_KEY}`);
  const snapshot = await object.json<ForecastSnapshot>();
  if (
    snapshot.schema_version !== 1 ||
    snapshot.model_status !== "ready" ||
    !snapshot.as_of ||
    !Array.isArray(snapshot.stations) ||
    snapshot.count !== snapshot.stations.length
  ) {
    throw new Error("Malformed R2 forecast snapshot");
  }
  return snapshot;
}

async function publicWhatIf(request: Request, env: Env, stationId: string) {
  const body = (await request.json()) as {
    source?: "taipei" | "new_taipei";
    precipitation?: number;
    precipitation_probability?: number;
  };
  if (!body.source) throw new Error("A station source is required");
  if (body.precipitation === undefined && body.precipitation_probability === undefined) {
    throw new Error("At least one scenario value is required");
  }
  const snapshot = await publicForecastSnapshot(env);
  const station = snapshot.stations.find(
    (candidate) => candidate.source === body.source && candidate.station_id === stationId,
  );
  if (!station) throw new Error("Station not found in the published forecast snapshot");
  const heavyRain =
    (body.precipitation ?? 0) >= 5 || (body.precipitation_probability ?? 0) >= 50;
  const scenarioPrediction = heavyRain
    ? station.heavy_rain_prediction
    : station.dry_prediction;
  return {
    station_id: station.station_id,
    baseline_prediction: station.predicted_bikes,
    scenario_prediction: scenarioPrediction,
    difference: Number((scenarioPrediction - station.predicted_bikes).toFixed(2)),
    interpretation: "Model response under controlled inputs; not a causal estimate.",
    forecast_as_of: snapshot.as_of,
  };
}

async function publicQualityStatus(env: Env) {
  const object = await env.RAW_BUCKET.get(QUALITY_OBJECT_KEY);
  if (!object) throw new Error(`Missing R2 quality object: ${QUALITY_OBJECT_KEY}`);
  const quality = await object.json<CollectionQuality>();
  assertQuality(quality);
  return {
    generated_at: quality.updated_at,
    quality_basis:
      "Live sanitized view of the private R2 collection-quality control object.",
    sources: {},
    scheduler_runs: {
      success: quality.complete_runs_since_tracking,
      partial_failure: quality.partial_failure_runs_since_tracking,
      failure: Math.max(
        quality.tracked_runs -
          quality.complete_runs_since_tracking -
          quality.partial_failure_runs_since_tracking,
        0,
      ),
      malformed: 0,
    },
    minimum_requirement: {
      official_start_at: quality.official_start_at || COLLECTION_START_AT,
      required_hours: quality.required_hours || REQUIRED_HOURS,
      observed_station_hours: quality.observed_hours,
      minimum_completeness: quality.minimum_required_completeness,
      observed_station_completeness: quality.minimum_station_completeness,
      five_days_met: quality.five_days_met,
      collection_quality_met: quality.collection_quality_met,
    },
  };
}

function assertQuality(value: CollectionQuality): void {
  const numericValues = [
    value.tracked_runs,
    value.complete_runs_since_tracking,
    value.partial_failure_runs_since_tracking,
    value.observed_hours,
    value.required_hours,
    value.minimum_station_completeness,
    value.minimum_required_completeness,
  ];
  if (
    !value.official_start_at ||
    !value.updated_at ||
    numericValues.some((item) => !Number.isFinite(item) || item < 0)
  ) {
    throw new Error("Malformed R2 collection-quality control object");
  }
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
