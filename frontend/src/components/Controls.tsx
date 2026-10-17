import { useState } from "react";
import { post } from "../api";
import type { SimState } from "../types";

type Props = { sim: SimState | null; selectedZone: string | null; onChanged: () => void };
const SIM = "/api/v1/simulation";

export function Controls({ sim, selectedZone, onChanged }: Props) {
  const [busy, setBusy] = useState(false);

  const act = async (path: string, body?: unknown) => {
    setBusy(true);
    try {
      await post(path, body);
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  return (
    <section className="card">
      <h3>Simulation controls</h3>
      <div className="row">
        {sim?.running ? (
          <button disabled={busy} onClick={() => act(`${SIM}/pause`)}>⏸ Pause</button>
        ) : (
          <button className="primary" disabled={busy} onClick={() => act(`${SIM}/start`)}>▶ Start</button>
        )}
        <button disabled={busy} onClick={() => act(`${SIM}/reset`)}>↺ Reset</button>
        <button
          className="danger"
          disabled={busy}
          onClick={() => act(`${SIM}/spike`, selectedZone ? { h3_id: selectedZone } : {})}
          title={selectedZone ? "Spike at the selected zone" : "Spike at the city center (select a zone to aim it)"}
        >
          🔥 Spike{sim && sim.spike_seconds_left > 0 ? ` (${sim.spike_seconds_left}s)` : ""}
        </button>
      </div>

      <div className="row">
        <span className="label">Demand: {sim?.demand_per_minute ?? "–"}/min</span>
        <button disabled={busy} onClick={() => act(`${SIM}/demand`, { factor: 0.67 })}>−</button>
        <button disabled={busy} onClick={() => act(`${SIM}/demand`, { factor: 1.5 })}>+</button>
      </div>

      <div className="row">
        <span className="label">Drivers: {sim?.driver_count ?? "–"}</span>
        <button disabled={busy} onClick={() => act(`${SIM}/drivers`, { delta: -10 })}>−10</button>
        <button disabled={busy} onClick={() => act(`${SIM}/drivers`, { delta: 10 })}>+10</button>
      </div>

      <div className="row">
        <label className="label">Matching every</label>
        <select
          value={sim?.matching_interval ?? 5}
          onChange={(e) => act(`${SIM}/params`, { matching_interval: Number(e.target.value) })}
        >
          {[2, 5, 10, 20].map((s) => <option key={s} value={s}>{s} s</option>)}
        </select>
      </div>

      <div className="row">
        <label className="label">Surge sensitivity</label>
        <select
          value={sim?.surge_sensitivity ?? 0.35}
          onChange={(e) => act(`${SIM}/params`, { surge_sensitivity: Number(e.target.value) })}
        >
          <option value={0.15}>Low</option>
          <option value={0.35}>Normal</option>
          <option value={0.7}>High</option>
        </select>
      </div>
    </section>
  );
}