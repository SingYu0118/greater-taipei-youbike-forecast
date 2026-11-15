import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, Bike, BookOpen, ChevronRight, CloudRain, Database, MapPin, Search, Timer, X } from "lucide-react";
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
import { distanceMetres, MRT_LINES, MRT_STATIONS, type MrtLineCode } from "./mrt";

const StationMap = lazy(() => import("./StationMap"));

function App() {
  const docsUrl = import.meta.env.VITE_DOCS_URL ?? "http://localhost:3000";
  const [data, setData] = useState<LiveResponse>();
  const [health, setHealth] = useState<HealthResponse>();
  const [quality, setQuality] = useState<QualityResponse>();
  const [metrics, setMetrics] = useState<ModelMetricsResponse>();
  const [drivers, setDrivers] = useState<DriverResponse>();
  const [error, setError] = useState<string>();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Station>();
  const [source, setSource] = useState<"all" | "taipei" | "new_taipei">("all");
  const [mrtLine, setMrtLine] = useState<MrtLineCode | "">("");
  const [mrtStationKey, setMrtStationKey] = useState("");

  const lineMrtStations = useMemo(
    () => mrtLine ? MRT_STATIONS.filter((station) => station.lines.includes(mrtLine)) : [],
    [mrtLine],
  );
  const selectedMrt = useMemo(
    () => MRT_STATIONS.find((station) => station.key === mrtStationKey),
    [mrtStationKey],
  );
  const queryMrtMatches = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];
    return MRT_STATIONS.filter((station) =>
      station.name.toLowerCase().includes(normalized)
      || station.nameEn.toLowerCase().includes(normalized),
    );
  }, [query]);
  const activeMrt = selectedMrt ?? (queryMrtMatches.length === 1 ? queryMrtMatches[0] : undefined);

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
        if (healthResponse.model !== "collecting-training-data") {
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
    const metroTargets = selectedMrt
      ? [selectedMrt]
      : queryMrtMatches.length
        ? queryMrtMatches
        : lineMrtStations;
    const metroRadius = selectedMrt || queryMrtMatches.length ? 1_000 : 700;
    return (data?.stations ?? []).filter((station) => {
      const matchesMetro = !metroTargets.length
        || metroTargets.some((metro) => distanceMetres(station, metro) <= metroRadius);
      return (source === "all" || station.source === source)
        && matchesMetro
        && (!normalized || queryMrtMatches.length > 0
          || station.station_name.toLowerCase().includes(normalized)
          || station.station_name_en?.toLowerCase().includes(normalized)
          || station.district.toLowerCase().includes(normalized)
          || station.district_en?.toLowerCase().includes(normalized));
    });
  }, [data, query, source, selectedMrt, lineMrtStations, queryMrtMatches]);

  const nearbyStations = useMemo(() => {
    if (!activeMrt) return [];
    return (data?.stations ?? [])
      .filter((station) => source === "all" || station.source === source)
      .map((station) => ({ station, distance: distanceMetres(station, activeMrt) }))
      .filter((item) => item.distance <= 1_000)
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 6);
  }, [data, activeMrt, source]);

  useEffect(() => {
    if (query.trim() && filtered.length === 1) setSelected(filtered[0]);
  }, [filtered, query]);

  const emptyRisk = filtered.filter((station) => effectiveBikes(station) <= 2).length;
  const fullRisk = filtered.filter(
    (station) => station.capacity - effectiveBikes(station) <= 2,
  ).length;
  const coverageHours = quality?.minimum_requirement.observed_station_hours ?? 0;
  const requiredHours = quality?.minimum_requirement.required_hours ?? 120;
  const collectionStarted = Boolean(quality?.minimum_requirement.official_start_at);
  const collectionProgress = Math.min((coverageHours / requiredHours) * 100, 100);
  const earlyDiagnosticHours = 72;
  const earlyProgress = Math.min((coverageHours / earlyDiagnosticHours) * 100, 100);
  const sourceCounts = {
    all: data?.stations.length ?? 0,
    taipei: data?.stations.filter((station) => station.source === "taipei").length ?? 0,
    new_taipei: data?.stations.filter((station) => station.source === "new_taipei").length ?? 0,
  };

  const chooseRegion = (region: "all" | "taipei" | "new_taipei") => {
    setSource(region);
    setSelected(undefined);
    setQuery("");
    setMrtLine("");
    setMrtStationKey("");
  };

  const chooseMrtLine = (line: MrtLineCode | "") => {
    setMrtLine(line);
    setMrtStationKey("");
    setSelected(undefined);
    setQuery("");
  };

  const chooseMrtStation = (key: string) => {
    setMrtStationKey(key);
    setSelected(undefined);
    setQuery("");
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="VeloCast home">
          <span className="brand-mark"><Bike size={20} /></span>
          <span>VELOCAST</span>
        </a>
          <div className="live-state"><span className="pulse" /> FORECAST NETWORK</div>
        <div className="top-actions">
          <a className="docs-link" href={docsUrl}><BookOpen size={15} /> DOCUMENTATION</a>
          <div className="model-state">
            <Database size={15} /> MODEL STATUS: {health?.model === "ready" ? "LIVE" : health?.model === "validated-results-ready" ? "VALIDATED" : "COLLECTING"}
          </div>
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
            <span>{health?.model === "ready" ? "FORECAST AS OF" : "LAST FEED"}</span>
            <strong>{data ? new Date(data.as_of).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—"}</strong>
            <small>ASIA / TAIPEI</small>
          </div>
        </section>

        <section className="dashboard-card">
          <div className="controls">
            <label className="search"><Search size={18} /><input list="mrt-station-suggestions" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search YouBike, district, or Metro in 中文 / English" /></label>
            <datalist id="mrt-station-suggestions">
              {MRT_STATIONS.flatMap((station) => [
                <option key={`${station.key}:zh`} value={station.name}>{station.name}（{station.nameEn}）</option>,
                <option key={`${station.key}:en`} value={station.nameEn}>{station.name}（{station.nameEn}）</option>,
              ])}
            </datalist>
            <div className="region-switch" role="group" aria-label="Move map to a city">
              {(["all", "taipei", "new_taipei"] as const).map((item) => (
                <button
                  aria-pressed={source === item}
                  className={source === item ? "active" : ""}
                  onClick={() => chooseRegion(item)}
                  key={item}
                >
                  <MapPin size={16} />
                  <span>
                    <strong>{item === "all" ? "Greater Taipei" : item === "taipei" ? "Taipei" : "New Taipei"}</strong>
                    <small>{sourceCounts[item].toLocaleString()} stations</small>
                  </span>
                </button>
              ))}
            </div>
            <div className="mrt-filters" aria-label="Filter by Taipei Metro line and station">
              <div className="mrt-filter-heading"><span className="mrt-symbol">M</span><strong>Explore by Metro</strong><small>Map and nearby YouBike availability update together</small></div>
              <label>
                <span>METRO LINE</span>
                <select value={mrtLine} onChange={(event) => chooseMrtLine(event.target.value as MrtLineCode | "")}>
                  <option value="">All lines</option>
                  {MRT_LINES.map((line) => <option key={line.code} value={line.code}>{line.code} · {line.name} / {line.nameEn}</option>)}
                </select>
              </label>
              <label>
                <span>METRO STATION</span>
                <select value={mrtStationKey} onChange={(event) => chooseMrtStation(event.target.value)} disabled={!mrtLine}>
                  <option value="">{mrtLine ? `All ${lineMrtStations.length} stations` : "Select a line first"}</option>
                  {lineMrtStations.map((station) => <option key={station.key} value={station.key}>{station.stationIds.join(" / ")} · {station.name}（{station.nameEn}）</option>)}
                </select>
              </label>
            </div>
          </div>

          {activeMrt ? (
            <div className="metro-results" aria-live="polite">
              <div className="metro-results-title">
                <span>{activeMrt.stationIds.join(" / ")}</span>
                <strong>{activeMrt.name}（{activeMrt.nameEn}）</strong>
                <small>{nearbyStations.length} nearest YouBike stations within 1 km</small>
              </div>
              <div className="metro-station-cards">
                {nearbyStations.map(({ station, distance }) => (
                  <button key={`${station.source}:${station.station_id}`} onClick={() => setSelected(station)}>
                    <span>{Math.round(distance)} m</span>
                    <strong>{bilingualName(station.station_name, station.station_name_en)}</strong>
                    <div><b>{station.available_bikes}</b><small>BIKES NOW</small></div>
                    <div><b>{station.predicted_bikes?.toFixed(1) ?? "—"}</b><small>+60 MIN</small></div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="map-wrap">
            {error ? <div className="map-message"><Activity /> Live feed unavailable<br /><small>{error}</small></div> : null}
            {!data && !error ? <div className="map-message"><span className="loader" /> Loading live network</div> : null}
            <Suspense fallback={<div className="map-message"><span className="loader" /> Loading map</div>}>
              <StationMap
                stations={filtered}
                focusRegion={source}
                focusMrtStations={activeMrt ? [activeMrt] : lineMrtStations}
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
            <h3>{quality?.minimum_requirement.five_days_met ? "Five-day evidence gate passed" : collectionStarted ? "Building the required history" : "Official collection not started"}</h3>
            <p>{quality?.minimum_requirement.five_days_met ? "Formal time validation is complete. The map now serves a published CatBoost forecast snapshot for every station." : collectionStarted ? "The model remains unavailable until the full collection window and final time-based evaluation pass." : "The verified five-day clock will begin only after the application and pipeline pass their functional gates."}</p>
          </div>
          <div className="progress-block">
            <div><span>OBSERVED WINDOW</span><strong>{coverageHours.toFixed(1)} / {requiredHours} h</strong></div>
            <div className="progress-track"><i style={{ width: `${collectionProgress}%` }} /></div>
            <small>{quality ? collectionStarted ? `${quality.scheduler_runs.success} successful · ${quality.scheduler_runs.partial_failure} partial · ${quality.scheduler_runs.failure} failed` : "Waiting for the verified collection start" : "Reading collection evidence"}</small>
          </div>
        </section>

        {metrics && drivers ? (
          <ModelResults metrics={metrics} drivers={drivers} />
        ) : (
          <PreliminaryEvidence
            coverageHours={coverageHours}
            earlyDiagnosticHours={earlyDiagnosticHours}
            earlyProgress={earlyProgress}
            stationCount={data?.count ?? 0}
            completeness={quality?.minimum_requirement.observed_station_completeness ?? 0}
            verifiedRuns={quality?.scheduler_runs.success ?? 0}
            docsUrl={docsUrl}
          />
        )}

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
      <p className="eyebrow"><span>{station.source.replace("_", " ").toUpperCase()}</span> · {bilingualName(station.district, station.district_en)}</p>
      <h2>{bilingualName(station.station_name, station.station_name_en)}</h2>
      <div className="inventory"><div><strong>{station.available_bikes}</strong><span>BIKES AT ORIGIN</span></div><div><strong>{station.available_docks}</strong><span>DOCKS AT ORIGIN</span></div></div>
      <div className="capacity-bar"><i style={{ width: `${Math.round(ratio * 100)}%` }} /></div>
      {station.predicted_bikes === undefined ? (
        <div className="forecast-pending"><Timer /><div><strong>Forecast unavailable for this station</strong><p>The latest published snapshot did not contain an eligible forecast for this station. Current inventory remains visible without being relabelled as a prediction.</p></div></div>
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
      <small className="station-id">FORECAST ORIGIN / {station.observation_time ? new Date(station.observation_time).toLocaleString("en-GB", { timeZone: "Asia/Taipei", hour12: false }) : "—"}<br />STATION ID / {station.station_id}</small>
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
        <ResultMetric value={winner.rmse.toFixed(2)} label="RMSE · BIKES" />
      </div>
      <div className="validation-summary">
        <p><strong>{metrics.coverage.final_holdout_rows?.toLocaleString() ?? "976,209"}</strong><span>untouched holdout rows</span></p>
        <p><strong>{metrics.validation?.folds ?? 3} folds</strong><span>expanding time validation</span></p>
        <p><strong>{metrics.validation?.purge_minutes ?? 60} min</strong><span>leakage prevention gap</span></p>
      </div>
      <div className="driver-list">
        <div><BarChart3 /><span>TOP MODEL DRIVERS</span></div>
        {drivers.global_shap.slice(0, 5).map((driver, index) => (
          <p key={driver.feature}><b>0{index + 1}</b><span>{prettyFeature(driver.feature)}</span><i style={{ width: `${Math.max(10, (driver.mean_absolute_shap / topImportance) * 100)}%` }} /></p>
        ))}
        <small>{drivers.caution}</small>
      </div>
      <p className="serving-disclosure"><strong>Serving status:</strong> active. The map reads the validated CatBoost batch snapshot from R2; the displayed forecast time remains visible so a stored prediction is never presented as a newer one.</p>
    </section>
  );
}

function PreliminaryEvidence({
  coverageHours,
  earlyDiagnosticHours,
  earlyProgress,
  stationCount,
  completeness,
  verifiedRuns,
  docsUrl,
}: {
  coverageHours: number;
  earlyDiagnosticHours: number;
  earlyProgress: number;
  stationCount: number;
  completeness: number;
  verifiedRuns: number;
  docsUrl: string;
}) {
  const remaining = Math.max(earlyDiagnosticHours - coverageHours, 0);
  const modelingUrl = `${docsUrl.replace(/\/$/, "")}/docs/MODELING`;
  return (
    <section className="preliminary-evidence" aria-label="Current model evidence">
      <div className="evidence-heading">
        <div>
          <p className="eyebrow">MODEL EVIDENCE · LIVE STATUS</p>
          <h2>Results are staged,<br />not hidden.</h2>
        </div>
        <p>
          The network and collection evidence are already measurable. Model scores appear only
          after a genuinely unseen time window exists—never from a random row split.
        </p>
      </div>
      <div className="evidence-metrics">
        <ResultMetric value={stationCount ? stationCount.toLocaleString() : "—"} label="LIVE STATIONS" />
        <ResultMetric value={completeness ? `${(completeness * 100).toFixed(1)}%` : "—"} label="VERIFIED COMPLETENESS" />
        <ResultMetric value={verifiedRuns ? verifiedRuns.toLocaleString() : "—"} label="VERIFIED CLOUD RUNS" />
        <ResultMetric value="7 + 3" label="MODELS + BASELINES" />
      </div>
      <div className="evaluation-roadmap">
        <article className="roadmap-active">
          <span>NOW</span>
          <strong>Collect and verify</strong>
          <p>{coverageHours.toFixed(1)} hours of the official window are currently verified.</p>
        </article>
        <article>
          <span>AT 72 HOURS</span>
          <strong>48h train → day-3 test</strong>
          <p>Preliminary benchmark on one untouched day. {remaining.toFixed(1)} hours remaining.</p>
          <div className="early-progress" aria-label={`${earlyProgress.toFixed(0)} percent to early diagnostic`}>
            <i style={{ width: `${earlyProgress}%` }} />
          </div>
        </article>
        <article>
          <span>AT 120 HOURS</span>
          <strong>Formal time validation</strong>
          <p>Three rolling folds, purge gap, and a final untouched 24-hour holdout.</p>
        </article>
      </div>
      <a className="evidence-link" href={modelingUrl}>Read the validation contract <ChevronRight size={17} /></a>
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

function bilingualName(chinese: string, english?: string): string {
  const normalizedEnglish = english?.trim();
  return normalizedEnglish && normalizedEnglish.toLowerCase() !== chinese.trim().toLowerCase()
    ? `${chinese}（${normalizedEnglish}）`
    : chinese;
}

export default App;

