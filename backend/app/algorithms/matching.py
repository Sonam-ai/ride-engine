"""Batch matching of riders to drivers.

Steps for one batch:
 1. Candidate filtering: for every request keep its K nearest drivers, and for every driver
    its K nearest requests, but only pairs within max_distance_km. This keeps the problem small.
 2. Cost for each candidate pair:
        cost = pickup_time_weight * pickup_ETA_minutes
             + distance_weight * distance_km
             - wait_priority_weight * minutes_the_rider_has_waited
    The wait term gives riders who waited longer a lower cost, so they win when drivers are scarce.
 3. Build a matrix with rows = requests and columns = drivers (only those that appear in some
    candidate pair). Pairs that are not candidates get BIG_COST.
 4. Solve the assignment problem with the Hungarian algorithm (scipy linear_sum_assignment).
    It minimises total cost, and BIG_COST is so large that it first maximises the number of
    real matches, then minimises total pickup cost.
 5. Throw away any assignment that landed on BIG_COST.

Complexity: filtering is O(R x D) with numpy; the Hungarian step is O(n^3) with n = max(rows, columns)
of the *filtered* matrix, not of the whole city.
Limitations: straight-line distance, no road network; one batch at a time; candidate K limits
can in rare cases leave a feasible far-away driver unused.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.core.config import settings
from app.spatial.distance import haversine_km, haversine_matrix_km

BIG_COST = 1e6


@dataclass(frozen=True)
class DriverPoint:
    driver_id: str
    lat: float
    lng: float


@dataclass(frozen=True)
class RequestPoint:
    ride_id: str
    lat: float
    lng: float
    wait_seconds: float


@dataclass(frozen=True)
class Assignment:
    ride_id: str
    driver_id: str
    distance_km: float
    eta_seconds: float
    cost: float


@dataclass(frozen=True)
class MatchingConfig:
    max_distance_km: float = 5.0
    k_nearest: int = 8
    pickup_speed_kmh: float = 25.0
    pickup_time_weight: float = 1.0
    distance_weight: float = 0.5
    wait_priority_weight: float = 0.2

    @classmethod
    def from_settings(cls) -> "MatchingConfig":
        return cls(
            settings.max_pickup_distance_km, settings.matching_k_nearest, settings.average_speed_kmh,
            settings.pickup_time_weight, settings.distance_weight, settings.wait_priority_weight,
        )

    def eta_seconds(self, distance_km: float) -> float:
        return distance_km / self.pickup_speed_kmh * 3600

    def cost(self, distance_km: float, wait_seconds: float) -> float:
        eta_minutes = self.eta_seconds(distance_km) / 60
        return (
            self.pickup_time_weight * eta_minutes
            + self.distance_weight * distance_km
            - self.wait_priority_weight * wait_seconds / 60
        )


def candidate_pairs(requests: list[RequestPoint], drivers: list[DriverPoint], cfg: MatchingConfig):
    """Returns (request_index, driver_index, distance_km) for plausible pairs only."""
    if not requests or not drivers:
        return []
    dist = haversine_matrix_km(
        np.array([r.lat for r in requests])[:, None], np.array([r.lng for r in requests])[:, None],
        np.array([d.lat for d in drivers])[None, :], np.array([d.lng for d in drivers])[None, :],
    )
    pairs: dict[tuple[int, int], float] = {}
    for ri in range(len(requests)):
        for di in np.argsort(dist[ri])[: cfg.k_nearest]:
            if dist[ri, di] <= cfg.max_distance_km:
                pairs[(ri, int(di))] = float(dist[ri, di])
    for di in range(len(drivers)):
        for ri in np.argsort(dist[:, di])[: cfg.k_nearest]:
            if dist[ri, di] <= cfg.max_distance_km:
                pairs[(int(ri), di)] = float(dist[ri, di])
    return [(ri, di, d) for (ri, di), d in sorted(pairs.items())]


def match_global(requests: list[RequestPoint], drivers: list[DriverPoint], cfg: MatchingConfig) -> list[Assignment]:
    pairs = candidate_pairs(requests, drivers, cfg)
    if not pairs:
        return []
    req_ids = sorted({p[0] for p in pairs})
    drv_ids = sorted({p[1] for p in pairs})
    rpos = {r: i for i, r in enumerate(req_ids)}
    dpos = {d: i for i, d in enumerate(drv_ids)}
    matrix = np.full((len(req_ids), len(drv_ids)), BIG_COST)
    info: dict[tuple[int, int], tuple[float, float]] = {}
    for ri, di, dist in pairs:
        cost = cfg.cost(dist, requests[ri].wait_seconds)
        matrix[rpos[ri], dpos[di]] = cost
        info[(ri, di)] = (dist, cost)

    rows, cols = linear_sum_assignment(matrix)
    result = []
    for r, c in zip(rows, cols):
        if matrix[r, c] >= BIG_COST:
            continue
        ri, di = req_ids[r], drv_ids[c]
        dist, cost = info[(ri, di)]
        result.append(Assignment(requests[ri].ride_id, drivers[di].driver_id, dist, cfg.eta_seconds(dist), cost))
    return result


def match_nearest_first(requests: list[RequestPoint], drivers: list[DriverPoint], cfg: MatchingConfig) -> list[Assignment]:
    """Naive baseline (first come, first served -> nearest free driver). Used only in tests
    to show that global matching gives a different, better result. The engine never calls it."""
    taken: set[str] = set()
    out = []
    for req in requests:
        best = None
        for d in drivers:
            if d.driver_id in taken:
                continue
            dist = haversine_km(req.lat, req.lng, d.lat, d.lng)
            if dist <= cfg.max_distance_km and (best is None or dist < best[1]):
                best = (d, dist)
        if best:
            d, dist = best
            taken.add(d.driver_id)
            out.append(Assignment(req.ride_id, d.driver_id, dist, cfg.eta_seconds(dist), cfg.cost(dist, req.wait_seconds)))
    return out