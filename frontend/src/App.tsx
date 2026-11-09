import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Activity, Bike, ChevronRight, CloudRain, Database, Search, Timer, X } from "lucide-react";
import { fetchStations } from "./api";
import type { LiveResponse, Station } from "./types";

const StationMap = lazy(() => import("./StationMap"));

function App() {
  const [data, setData] = useState<LiveResponse>();
  const [error, setError] = useState<string>();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Station>();
  const [source, setSource] = useState<"all" | "taipei" | "new_taipei">("all");

  useEffect(() => {
    const controller = new AbortController();
    fetchStations(controller.signal)
      .then((response) => {
        setData(response);
        setError(undefined);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
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

  const emptyRisk = filtered.filter((station) => station.available_bikes <= 2).length;
  const fullRisk = filtered.filter((station) => station.available_docks <= 2).length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="VeloCast home">
          <span className="brand-mark"><Bike size={20} /></span>
          <span>VELOCAST</span>
        </a>
        <div className="live-state"><span className="pulse" /> LIVE NETWORK</div>
        <div className="model-state"><Database size={15} /> MODEL STATUS: COLLECTING</div>
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
                selectedId={selected?.station_id}
                onSelect={setSelected}
              />
            </Suspense>
            <div className="legend"><span><i className="red" /> Empty risk</span><span><i className="amber" /> Low</span><span><i className="green" /> Available</span><span><i className="blue" /> Full risk</span></div>
            <div className="network-stats">
              <Stat value={filtered.length || "—"} label="VISIBLE STATIONS" />
              <Stat value={emptyRisk || "—"} label="EMPTY RISK" warning />
              <Stat value={fullRisk || "—"} label="FULL RISK" />
            </div>
          </div>
        </section>

        <section className="method-strip">
          <div><Timer /><span>HORIZON<strong>60 minutes</strong></span></div>
          <div><Activity /><span>VALIDATION<strong>Rolling origin</strong></span></div>
          <div><CloudRain /><span>WEATHER<strong>Issue-time forecast</strong></span></div>
          <a href="#methodology">View methodology <ChevronRight size={17} /></a>
        </section>

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
  return (
    <aside className="station-panel" aria-label="Selected station details">
      <button className="close" onClick={onClose} aria-label="Close details"><X /></button>
      <p className="eyebrow">{station.source.replace("_", " ")} · {station.district}</p>
      <h2>{station.station_name}</h2>
      <div className="inventory"><div><strong>{station.available_bikes}</strong><span>BIKES NOW</span></div><div><strong>{station.available_docks}</strong><span>OPEN DOCKS</span></div></div>
      <div className="capacity-bar"><i style={{ width: `${Math.round(ratio * 100)}%` }} /></div>
      <div className="forecast-pending"><Timer /><div><strong>Forecast training in progress</strong><p>The one-hour forecast will appear after the minimum history and final validation gates are complete.</p></div></div>
      <small className="station-id">STATION ID / {station.station_id}</small>
    </aside>
  );
}

export default App;

