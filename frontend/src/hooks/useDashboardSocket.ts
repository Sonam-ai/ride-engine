import { useEffect, useRef, useState } from "react";
import { WS_URL } from "../api";
import type { DriverPos, FeedItem } from "../types";

function describe(msg: any): string | null {
  const d = msg.data ?? {};
  switch (msg.event) {
    case "ride_requested":
      return `Ride requested near ${d.pickup_h3} · surge ×${d.surge_multiplier}`;
    case "driver_assigned":
      return `Driver ${d.driver_id} assigned to ride ${d.ride_id} · ETA ${Math.round(d.pickup_eta_seconds)}s`;
    case "ride_status_changed":
      return `Ride ${d.ride_id}: ${d.from} → ${d.to}`;
    case "surge_updated":
      return `Surge updated in ${d.zones?.length ?? 0} zones`;
    default:
      return null;
  }
}

export function useDashboardSocket() {
  // Drivers move many times a second, so we collect them in a ref and
  // copy them into React state twice a second instead of re-rendering per message.
  const driversRef = useRef(new Map<string, DriverPos>());
  const [drivers, setDrivers] = useState<DriverPos[]>([]);
  const [connected, setConnected] = useState(false);
  const [feed, setFeed] = useState<FeedItem[]>([]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryMs = 1000;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let counter = 0;

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        setConnected(true);
        retryMs = 1000;
      };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        const map = driversRef.current;
        if (msg.event === "snapshot") {
          map.clear();
          for (const d of msg.data.drivers) map.set(d.driver_id, d);
        } else if (msg.event === "driver_location_updated") {
          map.set(msg.data.driver_id, msg.data);
        } else if (msg.event === "driver_removed") {
          map.delete(msg.data.driver_id);
        } else if (msg.event === "simulation_reset") {
          map.clear();
        } else {
          const text = describe(msg);
          if (text) {
            const item = { id: ++counter, time: new Date(msg.timestamp).toLocaleTimeString(), text, kind: msg.event };
            setFeed((prev) => [item, ...prev].slice(0, 40));
          }
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stopped) {
          timer = setTimeout(connect, retryMs);
          retryMs = Math.min(retryMs * 2, 10000); // back off: 1s, 2s, 4s ... max 10s
        }
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    const flush = setInterval(() => setDrivers(Array.from(driversRef.current.values())), 500);
    return () => {
      stopped = true;
      clearTimeout(timer);
      clearInterval(flush);
      ws?.close();
    };
  }, []);

  return { drivers, connected, feed };
}