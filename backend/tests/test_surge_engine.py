import math

import pytest

from app.algorithms.surge import SurgePricingEngine

engine = SurgePricingEngine(1.0, 4.0, 0.3, 0.7, 0.3, 0.35, 1.0, 1)


def test_no_division_by_zero_when_there_are_no_drivers():
    assert engine.ratio(demand=5, supply=0) == 5.0
    assert engine.ratio(demand=0, supply=0) == 0.0


def test_balanced_or_quiet_zone_has_minimum_surge():
    assert engine.target_surge(0.0) == 1.0
    assert engine.target_surge(1.0) == 1.0


def test_target_surge_formula_value():
    expected = 1.0 + 3.0 * (1 - math.exp(-0.35 * 2.0))  # effective ratio 3 -> excess 2
    assert engine.target_surge(3.0) == pytest.approx(expected)


def test_surge_rises_with_demand_and_is_bounded():
    values = [engine.target_surge(r) for r in (0, 1, 2, 4, 8, 50, 10_000)]
    assert values == sorted(values)
    assert all(1.0 <= v <= 4.0 for v in values)
    assert engine.target_surge(10_000) == pytest.approx(4.0)


def test_temporal_smoothing_moves_part_of_the_way():
    assert engine.smooth(target=3.0, previous=1.0) == pytest.approx(1.6)  # 0.3*3 + 0.7*1


def test_neighbors_influence_the_effective_ratio():
    result = engine.compute(demand=0, supply=5, neighbor_ratios=[6.0] * 6, previous=1.0)
    assert result.local_ratio == 0
    assert result.effective_ratio == pytest.approx(0.3 * 6.0)  # 1.8 -> above balanced
    assert result.surge > 1.0


def test_isolated_spike_is_damped_by_calm_neighbors():
    alone = SurgePricingEngine(local_weight=1.0, neighbor_weight=0.0)
    smoothed = SurgePricingEngine(local_weight=0.7, neighbor_weight=0.3)
    a = alone.compute(15, 5, [0.0] * 6, 1.0)
    b = smoothed.compute(15, 5, [0.0] * 6, 1.0)
    assert b.target_surge < a.target_surge


def test_same_inputs_give_same_output():
    assert engine.compute(9, 3, [1.0] * 6, 1.4) == engine.compute(9, 3, [1.0] * 6, 1.4)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"alpha": 0.0},
        {"alpha": 1.5},
        {"local_weight": 0.5, "neighbor_weight": 0.2},
        {"min_surge": 3.0, "max_surge": 2.0},
        {"sensitivity": 0.0},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        SurgePricingEngine(**kwargs)