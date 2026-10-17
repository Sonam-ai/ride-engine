import { useState } from "react";
import { get } from "./api";
import { Controls } from "./components/Controls";
import { DetailCard } from "./components/DetailCard";
import { MapView } from "./components/MapView";
import { EventFeed, StatsPanel } from "./components/SidePanel";
import { useDashboardSocket } from "./hooks/useDashboardSocket";
import { usePolling } from "./hooks/usePolling";
import type { Ride, SimState, Stats, Zone } from "./types";

export default function App() {
  const { drivers, connected, feed } = useDashboardSocket(); // live driver movement (WebSocket)
  const zones = usePolling(() => get<Zone[]>("/api/v1/zones"), 3000);
  const rides = usePolling(() => get<Ride[]>("/api/v1/rides/live"), 2000);
  const stats = usePolling(() => get<Stats>("/api/v1/stats"), 2000);
  const sim = usePolling(() => get<SimState>("/api/v1/simulation/state"), 3000);

  const [zoneId, setZoneId] = useState<string | null>(null);
  const [rideId, setRideId] = useState<string | null>(null);

  const zone = zones.data?.find((z) => z.h3_id === zoneId) ?? null;
  const ride = rides.data?.find((r) => r.ride_id === rideId) ?? null;
  const backendDown = stats.error !== null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">⬡</span> Ride Engine <span className="muted">· live matching &amp; dynamic pricing</span>
        </div>
        <div className="badges">
          <span className={`badge ${connected ? "ok" : "bad"}`}>{connected ? "● live" : "○ reconnecting"}</span>
          <span className={`badge ${sim.data?.running ? "ok" : ""}`}>{sim.data?.running ? "simulation running" : "simulation paused"}</span>
        </div>
      </header>

      <main className="main">
        <div className="map-wrap">
          <MapView
            zones={zones.data ?? []}
            drivers={drivers}
            rides={rides.data ?? []}
            selectedZone={zoneId}
            selectedRide={rideId}
            onSelectZone={(id) => { setZoneId(id); setRideId(null); }}
            onSelectRide={(id) => { setRideId(id); setZoneId(null); }}
          />
          {backendDown && <div className="banner">Backend not reachable on {import.meta.env.VITE_API_URL ?? "http://localhost:8000"}</div>}
          <div className="legend">
            <div className="legend-title">Surge</div>
            <div className="legend-bar" />
            <div className="legend-scale"><span>×1.0</span><span>×2.5</span><span>×4.0</span></div>
            <div className="legend-items">
              <span><i style={{ background: "#3ddc97" }} />free driver</span>
              <span><i style={{ background: "#4dabf7" }} />busy driver</span>
              <span><i style={{ background: "#ff6b9d" }} />waiting rider</span>
              <span><i style={{ background: "#ffd43b" }} />driver coming</span>
            </div>
          </div>
        </div>

        <aside className="panel">
          <Controls sim={sim.data} selectedZone={zoneId} onChanged={sim.refresh} />
          <StatsPanel stats={stats.data} />
          <DetailCard zone={zone} ride={ride} onClose={() => { setZoneId(null); setRideId(null); }} />
          <EventFeed feed={feed} />
        </aside>
      </main>
    </div>
  );
}