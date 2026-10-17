import type { FeedItem, Stats } from "../types";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function StatsPanel({ stats }: { stats: Stats | null }) {
  if (!stats) return <section className="card"><h3>System</h3><p className="muted">Loading…</p></section>;
  return (
    <section className="card">
      <h3>System</h3>
      <div className="stats-grid">
        <Stat label="Drivers" value={stats.drivers.total} hint={`${stats.drivers.available} free · ${stats.drivers.busy} busy`} />
        <Stat label="Pending requests" value={stats.open_requests} />
        <Stat label="Active rides" value={stats.active_rides} />
        <Stat label="Completed" value={stats.completed_trips} hint={`${stats.cancelled_trips + stats.expired_requests} cancelled/expired`} />
        <Stat label="Avg pickup ETA" value={stats.avg_pickup_eta_seconds == null ? "–" : `${Math.round(stats.avg_pickup_eta_seconds)} s`} />
        <Stat label="Avg matching time" value={stats.avg_matching_seconds == null ? "–" : `${stats.avg_matching_seconds} s`} />
        <Stat label="Average surge" value={`×${stats.average_surge.toFixed(2)}`} />
        <Stat
          label="Highest surge zone"
          value={stats.highest_surge_zone ? `×${stats.highest_surge_zone.surge_multiplier.toFixed(2)}` : "–"}
          hint={stats.highest_surge_zone?.h3_id}
        />
      </div>
    </section>
  );
}

export function EventFeed({ feed }: { feed: FeedItem[] }) {
  return (
    <section className="card feed">
      <h3>Live events</h3>
      {feed.length === 0 && <p className="muted">Waiting for events… press Start.</p>}
      <ul>
        {feed.map((item) => (
          <li key={item.id} className={`feed-${item.kind}`}>
            <span className="feed-time">{item.time}</span> {item.text}
          </li>
        ))}
      </ul>
    </section>
  );
}