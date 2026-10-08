import math
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class SurgeResult:
    local_ratio: float
    neighbor_ratio: float
    effective_ratio: float
    target_surge: float  # what the formula says right now
    surge: float  # after temporal smoothing: what riders actually pay


class SurgePricingEngine:
    """Turns supply/demand into a bounded, smoothed price multiplier.

    1. local_ratio    = demand / max(supply, min_supply)         (never divides by zero)
    2. neighbor_ratio = mean ratio of the 6 neighboring cells
    3. effective      = local_weight * local + neighbor_weight * neighbor
    4. target         = min + (max - min) * (1 - exp(-sensitivity * max(0, effective - balanced)))
                        -> 1.0 while supply covers demand, rises smoothly, saturates at max
    5. surge          = alpha * target + (1 - alpha) * previous   (temporal smoothing / EMA)
    """

    def __init__(
        self,
        min_surge: float = 1.0,
        max_surge: float = 4.0,
        alpha: float = 0.3,
        local_weight: float = 0.7,
        neighbor_weight: float = 0.3,
        sensitivity: float = 0.35,
        balanced_ratio: float = 1.0,
        min_supply: int = 1,
    ) -> None:
        if min_surge <= 0 or max_surge < min_surge:
            raise ValueError("need 0 < min_surge <= max_surge")
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        if local_weight < 0 or neighbor_weight < 0 or abs(local_weight + neighbor_weight - 1) > 1e-9:
            raise ValueError("local_weight + neighbor_weight must equal 1")
        if sensitivity <= 0 or min_supply < 1:
            raise ValueError("sensitivity must be > 0 and min_supply >= 1")
        self.min_surge, self.max_surge, self.alpha = min_surge, max_surge, alpha
        self.local_weight, self.neighbor_weight = local_weight, neighbor_weight
        self.sensitivity, self.balanced_ratio, self.min_supply = sensitivity, balanced_ratio, min_supply

    @classmethod
    def from_settings(cls) -> "SurgePricingEngine":
        return cls(
            settings.surge_min, settings.surge_max, settings.surge_alpha,
            settings.surge_local_weight, settings.surge_neighbor_weight,
            settings.surge_sensitivity, settings.surge_balanced_ratio, settings.surge_min_supply,
        )

    def _clamp(self, value: float) -> float:
        return min(self.max_surge, max(self.min_surge, value))

    def ratio(self, demand: int, supply: int) -> float:
        return demand / max(supply, self.min_supply)

    def target_surge(self, effective_ratio: float) -> float:
        excess = max(0.0, effective_ratio - self.balanced_ratio)
        span = self.max_surge - self.min_surge
        return self._clamp(self.min_surge + span * (1 - math.exp(-self.sensitivity * excess)))

    def smooth(self, target: float, previous: float) -> float:
        return self._clamp(self.alpha * target + (1 - self.alpha) * self._clamp(previous))

    def compute(self, demand: int, supply: int, neighbor_ratios: list[float], previous: float) -> SurgeResult:
        local = self.ratio(demand, supply)
        neighbor = sum(neighbor_ratios) / len(neighbor_ratios) if neighbor_ratios else local
        effective = self.local_weight * local + self.neighbor_weight * neighbor
        target = self.target_surge(effective)
        return SurgeResult(
            local_ratio=round(local, 4),
            neighbor_ratio=round(neighbor, 4),
            effective_ratio=round(effective, 4),
            target_surge=round(target, 4),
            surge=round(self.smooth(target, previous), 4),
        )