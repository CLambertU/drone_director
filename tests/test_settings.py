import pytest
from pydantic import ValidationError

from backend.config.settings import Settings


@pytest.mark.parametrize("values", [
    {"cost_weight_distance": -1}, {"cost_weight_weather": float("inf")},
    {"simulation_tick_seconds": 0}, {"simulation_default_speed": -1},
    {"conflict_horizontal_separation_m": 0}, {"port": 70000},
])
def test_invalid_settings_fail_at_startup(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_zero_cost_weight_is_valid():
    assert Settings(_env_file=None, cost_weight_distance=0).cost_weight_distance == 0
