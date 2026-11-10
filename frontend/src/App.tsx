import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, Bike, ChevronRight, CloudRain, Database, Search, Timer, X } from "lucide-react";
import {
  fetchDrivers,
  fetchForecasts,
  fetchHealth,
  fetchModelMetrics,
  fetchQuality,
  fetchStations,
  runWhatIf,
} from "./api";
import type {
  DriverResponse,
  HealthResponse,
  LiveResponse,
  ModelMetricsResponse,
  QualityResponse,
  Station,
  WhatIfResponse,
} from "./types";

const StationMap = lazy(() => import("./StationMap"));

function App() {
  const [data, setData] = useState<LiveResponse>();
  const [health, setHealth] = useState<HealthResponse>();
  const [quality, setQuality] = useState<QualityResponse>();
  const [metrics, setMetrics] = useState<ModelMetricsResponse>();
  const [drivers, setDrivers] = useState<DriverResponse>();
  const [error, setError] = useState<string>();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Station>();
  const [source, setSource] = useState<"all" | "taipei" | "new_taipei">("all");

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const [healthResponse, qualityResponse] = await Promise.all([
          fetchHealth(controller.signal),
          fetchQuality(controller.signal),
        ]);
        setHealth(healthResponse);
        setQuality(qualityResponse);
        const stationResponse = healthResponse.model === "ready"
          ? await fetchForecasts(controller.signal)
          : await fetchStations(controller.signal);
        setData(stationResponse);
        if (healthResponse.model === "ready") {
          const [metricResponse, driverResponse] = await Promise.all([
            fetchModelMetrics(controller.signal),
            fetchDrivers(controller.signal),
          ]);
          setMetrics(metricResponse);
          setDrivers(driverResponse);
        }
        setError(undefined);
      } catch (reason) {
        if (reason instanceof Error && reason.name !== "AbortError") setError(reason.message);
      }
    };
    void load();
    const interval = window.setInterval(() => void load(), 60_000);
    return () => {
      window.clearInterval(interval);
      controller.abort();
    };
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (data?.stations ?? []).filter(
      (station) =>
        (source === "all" || station.source === source) &&
        (!normalized ||
          station.station_name.toLowerCase().includes(normalized) ||
          station.district.toLowerCase().includes(normalized)),
    );
  }, [data, query, source]);

  const emptyRisk = filtered.filter((station) => effectiveBikes(station) <= 2).length;
  const fullRisk = filtered.filter(
    (station) => station.capacity - effectiveBikes(station) <= 2,
  ).length;
  const coverageHours = quality?.minimum_requirement.observed_station_hours ?? 0;
  const requiredHours = quality?.minimum_requirement.required_hours ?? 120;
  const collectionStarted = Boolean(quality?.minimum_requirement.official_start_at);
  const collectionProgress = Math.min((coverageHours / requiredHours) * 100, 100);

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="VeloCast home">
          <span className="brand-mark"><Bike size={20} /></span>
          <span>VELOCAST</span>
        </a>
        <div className="live-state"><span className="pulse" /> LIVE NETWORK</div>
        <div className="model-state">
          <Database size={15} /> MODEL STATUS: {health?.model === "ready" ? "READY" : "COLLECTING"}
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div>
            <p className="eyebrow">GREATER TAIPEI · ONE HOUR AHEAD</p>
            <h1>Know where the bikes<br /><em>will be.</em></h1>
            <p className="hero-copy">
              A leakage-safe forecasting system for every YouBike station across Taipei and New Taipei.
            </p>
          </div>
          <div className="hero-meta">
            <span>LAST FEED</span>
            <strong>{data ? new Date(data.as_of).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—"}</strong>
            <small>ASIA / TAIPEI</small>
          </div>
        </section>

        <section className="dashboard-card">
          <div className="controls">
            <label className="search"><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search station or district" /></label>
            <div className="segmented">
              {(["all", "taipei", "new_taipei"] as const).map((item) => (
                <button className={source === item ? "active" : ""} onClick={() => setSource(item)} key={item}>
                  {item === "all" ? "All" : item === "taipei" ? "Taipei" : "New Taipei"}
                </button>
              ))}
            </div>
          </div>

          <div className="map-wrap">
            {error ? <div className="map-message"><Activity /> Live feed unavailable<br /><small>{error}</small></div> : null}
            {!data && !error ? <div className="map-message"><span className="loader" /> Loading live network</div> : null}
            <Suspense fallback={<div className="map-message"><span className="loader" /> Loading map</div>}>
              <StationMap
                stations={filtered}
                selectedId={selected ? `${selected.source}:${selected.station_id}` : undefined}
                onSelect={setSelected}
              />
            </Suspense>
            <div className="legend"><span><i className="red" /> Empty risk</span><span><i className="amber" /> Low</span><span><i className="green" /> Available</span><span><i className="blue" /> Full risk</span></div>
            <div className="network-stats">
              <Stat value={filtered.length || "—"} label="VISIBLE STATIONS" />
              <Stat value={emptyRisk || "—"} label={health?.model === "ready" ? "PREDICTED EMPTY" : "EMPTY NOW"} warning />
              <Stat value={fullRisk || "—"} label={health?.model === "ready" ? "PREDICTED FULL" : "FULL NOW"} />
            </div>
          </div>
        </section>

        <section className="method-strip">
          <div><Timer /><span>HORIZON<strong>60 minutes</strong></span></div>
          <div><Activity /><span>VALIDATION<strong>Rolling origin</strong></span></div>
          <div><CloudRain /><span>WEATHER<strong>Issue-time forecast</strong></span></div>
          <a href="#methodology">View methodology <ChevronRight size={17} /></a>
        </section>

        <section className="collection-status" aria-label="Collection evidence gate">
          <div>
            <p className="eyebrow">EVIDENCE GATE</p>
            <h3>{quality?.minimum_requirement.five_days_met ? "Five-day history complete" : collectionStarted ? "Building the required history" : "Official collection not started"}</h3>
            <p>{collectionStarted ? "The model remains unavailable until the full collection window and final time-based evaluation pass." : "The verified five-day clock will begin only after the application and pipeline pass their functional gates."}</p>
          </div>
          <div className="progress-block">
            <div><span>OBSERVED WINDOW</span><strong>{coverageHours.toFixed(1)} / {requiredHours} h</strong></div>
            <div className="progress-track"><i style={{ width: `${collectionProgress}%` }} /></div>
            <small>{quality ? collectionStarted ? `${quality.scheduler_runs.success} successful · ${quality.scheduler_runs.partial_failure} partial · ${quality.scheduler_runs.failure} failed` : "Waiting for the verified collection start" : "Reading collection evidence"}</small>
          </div>
        </section>

        {metrics && drivers ? <ModelResults metrics={metrics} drivers={drivers} /> : null}

        <section id="methodology" className="explain-section">
          <p className="eyebrow">DESIGNED FOR TRUST</p>
          <h2>A forecast is only useful<br />when its evidence holds up.</h2>
          <div className="explain-grid">
            <article><span>01</span><h3>No future leakage</h3><p>Every feature is reconstructed as it would have been known at prediction time, including archived weather forecasts.</p></article>
            <article><span>02</span><h3>Models earn their place</h3><p>Baselines, linear models and tree ensembles compete across expanding time windows before one final untouched test.</p></article>
            <article><span>03</span><h3>Drivers, not guesses</h3><p>Global and local SHAP explanations show how time, rain, recent flow and nearby stations shape each result.</p></article>
          </div>
        </section>
      </main>

      {selected ? <StationPanel station={selected} onClose={() => setSelected(undefined)} /> : null}
      <footer><span>VELOCAST / 2026</span><span>DATA: TAIPEI & NEW TAIPEI OPEN DATA</span><span>FORECASTS ARE DECISION SUPPORT, NOT GUARANTEES.</span></footer>
    </div>
  );
}

function Stat({ value, label, warning = false }: { value: number | string; label: string; warning?: boolean }) {
  return <div className={warning ? "stat warning" : "stat"}><strong>{value}</strong><span>{label}</span></div>;
}

function StationPanel({ station, onClose }: { station: Station; onClose: () => void }) {
  const ratio = station.capacity ? station.available_bikes / station.capacity : 0;
  const [scenario, setScenario] = useState<WhatIfResponse>();
  const [scenarioError, setScenarioError] = useState<string>();
  const [scenarioLoading, setScenarioLoading] = useState(false);

  const simulate = async (precipitation: number, precipitationProbability: number) => {
    setScenarioLoading(true);
    setScenarioError(undefined);
    try {
      setScenario(await runWhatIf(station.source, station.station_id, {
        precipitation,
        precipitation_probability: precipitationProbability,
      }));
    } catch (reason) {
      setScenarioError(reason instanceof Error ? reason.message : "Scenario failed");
    } finally {
      setScenarioLoading(false);
    }
  };
  return (
    <aside className="station-panel" aria-label="Selected station details">
      <button className="close" onClick={onClose} aria-label="Close details"><X /></button>
      <p className="eyebrow">{station.source.replace("_", " ")} · {station.district}</p>
      <h2>{station.station_name}</h2>
      <div className="inventory"><div><strong>{station.available_bikes}</strong><span>BIKES NOW</span></div><div><strong>{station.available_docks}</strong><span>OPEN DOCKS</span></div></div>
      <div className="capacity-bar"><i style={{ width: `${Math.round(ratio * 100)}%` }} /></div>
      {station.predicted_bikes === undefined ? (
        <div className="forecast-pending"><Timer /><div><strong>Forecast training in progress</strong><p>The one-hour forecast will appear after the minimum history and final validation gates are complete.</p></div></div>
      ) : (
        <div className="forecast-ready">
          <div className="forecast-heading"><Timer /><span>ONE HOUR AHEAD</span></div>
          <strong>{station.predicted_bikes.toFixed(1)} <small>bikes</small></strong>
          <p>90% empirical error band: {station.prediction_low?.toFixed(1)}–{station.prediction_high?.toFixed(1)}</p>
          <div className="scenario-controls">
            <span>WEATHER WHAT-IF</span>
            <button disabled={scenarioLoading} onClick={() => void simulate(0, 10)}>Dry</button>
            <button disabled={scenarioLoading} onClick={() => void simulate(10, 90)}>Heavy rain</button>
          </div>
          {scenario ? <p className="scenario-result">Scenario: {scenario.scenario_prediction.toFixed(1)} bikes <b>{formatSigned(scenario.difference)}</b></p> : null}
          {scenarioError ? <p className="scenario-error">{scenarioError}</p> : null}
        </div>
      )}
      <small className="station-id">STATION ID / {station.station_id}</small>
    </aside>
  );
}

function ModelResults({ metrics, drivers }: { metrics: ModelMetricsResponse; drivers: DriverResponse }) {
  const winner = metrics.final_holdout[metrics.winner];
  const baseline = metrics.final_holdout.baseline_persistence;
  const improvement = baseline?.mae
    ? ((baseline.mae - winner.mae) / baseline.mae) * 100
    : 0;
  const topImportance = drivers.global_shap[0]?.mean_absolute_shap || 1;
  return (
    <section className="model-results" aria-label="Validated model results">
      <div className="results-intro">
        <p className="eyebrow">UNTOUCHED FINAL HOLDOUT</p>
        <h2>{prettyFeature(metrics.winner)} won the time-based competition.</h2>
        <p>Selected only from rolling validation, then evaluated once on the final 24 hours.</p>
      </div>
      <div className="metric-grid">
        <ResultMetric value={winner.mae.toFixed(2)} label="MAE · BIKES" />
        <ResultMetric value={`${improvement.toFixed(1)}%`} label="VS PERSISTENCE" />
        <ResultMetric value={`${(winner.empty_recall * 100).toFixed(0)}%`} label="EMPTY RECALL" />
      </div>
      <div className="driver-list">
        <div><BarChart3 /><span>TOP MODEL DRIVERS</span></div>
        {drivers.global_shap.slice(0, 5).map((driver, index) => (
          <p key={driver.feature}><b>0{index + 1}</b><span>{prettyFeature(driver.feature)}</span><i style={{ width: `${Math.max(10, (driver.mean_absolute_shap / topImportance) * 100)}%` }} /></p>
        ))}
        <small>{drivers.caution}</small>
      </div>
    </section>
  );
}

function ResultMetric({ value, label }: { value: string; label: string }) {
  return <div><strong>{value}</strong><span>{label}</span></div>;
}

function effectiveBikes(station: Station): number {
  return station.predicted_bikes ?? station.available_bikes;
}

function prettyFeature(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatSigned(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

export default App;

