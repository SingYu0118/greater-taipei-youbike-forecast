import type {
  DriverResponse,
  HealthResponse,
  LiveResponse,
  ModelMetricsResponse,
  QualityResponse,
  WhatIfResponse,
} from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchStations(signal?: AbortSignal): Promise<LiveResponse> {
  const response = await fetch(`${apiBase}/api/v1/stations/live`, { signal });
  if (!response.ok) {
    throw new Error(`Station service returned ${response.status}`);
  }
  return response.json() as Promise<LiveResponse>;
}

export async function fetchForecasts(signal?: AbortSignal): Promise<LiveResponse> {
  const response = await fetch(`${apiBase}/api/v1/forecasts/latest`, { signal });
  if (!response.ok) throw new Error(`Forecast service returned ${response.status}`);
  return response.json() as Promise<LiveResponse>;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBase}/health`, { signal });
  if (!response.ok) throw new Error(`Health service returned ${response.status}`);
  return response.json() as Promise<HealthResponse>;
}

export async function fetchQuality(signal?: AbortSignal): Promise<QualityResponse> {
  const response = await fetch(`${apiBase}/api/v1/data/quality`, { signal });
  if (!response.ok) throw new Error(`Quality service returned ${response.status}`);
  return response.json() as Promise<QualityResponse>;
}

export async function fetchModelMetrics(signal?: AbortSignal): Promise<ModelMetricsResponse> {
  const response = await fetch(`${apiBase}/api/v1/model/metrics`, { signal });
  if (!response.ok) throw new Error(`Model metrics returned ${response.status}`);
  return response.json() as Promise<ModelMetricsResponse>;
}

export async function fetchDrivers(signal?: AbortSignal): Promise<DriverResponse> {
  const response = await fetch(`${apiBase}/api/v1/model/drivers`, { signal });
  if (!response.ok) throw new Error(`Model drivers returned ${response.status}`);
  return response.json() as Promise<DriverResponse>;
}

export async function runWhatIf(
  source: "taipei" | "new_taipei",
  stationId: string,
  values: { precipitation: number; precipitation_probability: number },
): Promise<WhatIfResponse> {
  const response = await fetch(`${apiBase}/api/v1/stations/${encodeURIComponent(stationId)}/what-if`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, ...values }),
  });
  if (!response.ok) throw new Error(`Scenario service returned ${response.status}`);
  return response.json() as Promise<WhatIfResponse>;
}

