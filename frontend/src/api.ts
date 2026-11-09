import type { LiveResponse } from "./types";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchStations(signal?: AbortSignal): Promise<LiveResponse> {
  const response = await fetch(`${apiBase}/api/v1/stations/live`, { signal });
  if (!response.ok) {
    throw new Error(`Station service returned ${response.status}`);
  }
  return response.json() as Promise<LiveResponse>;
}

