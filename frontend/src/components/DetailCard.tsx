import type { Ride, Zone } from "../types";

function Row({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="detail-row">
      <span>{k}</span>
      <strong>{v}</strong>
    </div>
  );
}

export function DetailCard({ zone, ride, onClose }: { zone: Zone | null; ride: Ride | null; onClose: () => void }) {
  if (!zone && !ride) {
    return (
      <section className="card">
        <h3>Details</h3>
        <p className="muted">Click a hexagon or a pink pickup dot on the map.</p>
      </section>
    );
  }
  return (
    <section className="card">
      <h3>
        {ride ? "Ride details" : "Zone details"}
        <button className="link" onClick={onClose}>close</button>
      </h3>
      {ride && (
        <>
          <Row k="Ride" v={ride.ride_id} />
          <Row k="Rider" v={ride.rider_id} />
          <Row k="Status" v={ride.status} />
          <Row k="Pickup" v={`${ride.pickup_lat.toFixed(4)}, ${ride.pickup_lng.toFixed(4)}`} />
          <Row k="Destination" v={`${ride.dest_lat.toFixed(4)}, ${ride.dest_lng.toFixed(4)}`} />
          <Row k="Driver" v={ride.driver_id ?? "not assigned yet"} />
          <Row k="Pickup ETA" v={ride.pickup_eta_seconds ? `${Math.round(ride.pickup_eta_seconds)} s` : "–"} />
          <Row k="Surge" v={ride.surge_multiplier ? `×${ride.surge_multiplier.toFixed(2)}` : "–"} />
          <Row k="Fare" v={ride.quoted_fare ? `₹${ride.quoted_fare.toFixed(2)}` : "–"} />
        </>
      )}
      {zone && !ride && (
        <>
          <Row k="H3 cell" v={zone.h3_id} />
          <Row k="Level" v={zone.surge_level.replace("_", " ")} />
          <Row k="Surge multiplier" v={`×${zone.surge_multiplier.toFixed(2)}`} />
          <Row k="Supply (free drivers)" v={zone.available_drivers} />
          <Row k="Active drivers" v={zone.total_drivers} />
          <Row k="Demand (pending requests)" v={zone.open_requests} />
          <Row k="Demand / supply" v={zone.demand_supply_ratio.toFixed(2)} />
          <Row k="Effective ratio (smoothed)" v={zone.effective_ratio.toFixed(2)} />
        </>
      )}
    </section>
  );
}