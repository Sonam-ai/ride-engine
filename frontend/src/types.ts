export type Zone = {
  h3_id: string;
  total_drivers: number;
  available_drivers: number;
  open_requests: number;
  demand_supply_ratio: number;
  surge_multiplier: number;
  effective_ratio: number;
  surge_level: string;
};

export type Ride = {
  ride_id: string;
  rider_id: string;
  pickup_lat: number;
  pickup_lng: number;
  pickup_h3: string;
  dest_lat: number;
  dest_lng: number;
  status: string;
  quoted_fare: number | null;
  surge_multiplier: number | null;
  distance_km: number | null;
  pickup_eta_seconds: number | null;
  driver_id: string | null;
};

export type DriverPos = {
  driver_id: string;
  latitude: number;
  longitude: number;
  status: string;
  h3_cell: string;
};

export type Stats = {
  drivers: { total: number; available: number; busy: number; offline: number; stale: number };
  open_requests: number;
  active_rides: number;
  completed_trips: number;
  cancelled_trips: number;
  expired_requests: number;
  total_matches: number;
  avg_pickup_eta_seconds: number | null;
  avg_matching_seconds: number | null;
  average_surge: number;
  highest_surge_zone: { h3_id: string; surge_multiplier: number } | null;
};

export type SimState = {
  running: boolean;
  demand_per_minute: number;
  driver_count: number;
  spike_seconds_left: number;
  matching_interval: number;
  surge_sensitivity: number;
};

export type FeedItem = { id: number; time: string; text: string; kind: string };