"""
Cost Benchmark & Financial Analysis Tool
Compares Uncontrolled Charging vs. Smart Optimized Charging across various tariff scenarios.
"""

from typing import Dict, Any
from .ev_optimizer import EVChargingOptimizer, EVSpecs, GridEnvironment
from .tariff_models import StandardTOUTariff, SolarIncentiveTariff, DynamicRealTimeTariff


def run_benchmark(
    battery_kwh: float = 60.0,
    current_soc: float = 20.0,
    target_soc: float = 85.0,
    charger_kw: float = 7.4,
    arrival_hour: int = 18,
    departure_hour: int = 7,
    solar_peak_kw: float = 4.0,
    tariff_type: str = "standard_tou"
) -> Dict[str, Any]:
    """Runs a complete cost benchmark comparing uncontrolled vs smart charging."""
    # Build solar generation curve (peaking at noon)
    solar_curve = []
    for h in range(24):
        if 6 <= h <= 18:
            import numpy as np
            val = solar_peak_kw * np.sin((h - 6) * np.pi / 12) ** 2
            solar_curve.append(round(float(val), 2))
        else:
            solar_curve.append(0.0)

    # Select tariff
    if tariff_type == "solar_tou":
        tariff_model = SolarIncentiveTariff()
    elif tariff_type == "dynamic_spot":
        tariff_model = DynamicRealTimeTariff()
    else:
        tariff_model = StandardTOUTariff()

    rates = tariff_model.get_hourly_rates()

    ev_specs = EVSpecs(
        battery_capacity_kwh=battery_kwh,
        current_soc_percent=current_soc,
        target_soc_percent=target_soc,
        max_charge_power_kw=charger_kw,
        arrival_hour=arrival_hour,
        departure_hour=departure_hour,
    )

    grid_env = GridEnvironment(
        hourly_tariffs=rates,
        solar_generation_kw=solar_curve,
        grid_power_limit_kw=11.0,
    )

    optimizer = EVChargingOptimizer(ev_specs, grid_env)
    results = optimizer.solve()
    results["tariff_name"] = tariff_model.name
    results["currency"] = tariff_model.currency
    return results


if __name__ == "__main__":
    res = run_benchmark()
    currency = "INR " if res['currency'] == "₹" else f"{res['currency']} "
    print("=" * 60)
    print("SMART EV CHARGING OPTIMIZATION BENCHMARK REPORT")
    print("=" * 60)
    print(f"Tariff Model: {res['tariff_name']}")
    print(f"Energy Needed: {res['energy_needed_kwh']} kWh")
    print(f"Uncontrolled Charging Cost: {currency}{res['uncontrolled']['total_cost']}")
    print(f"Smart Optimized Cost:       {currency}{res['optimized']['total_cost']}")
    print(f"Total Monetary Savings:     {currency}{res['comparison']['cost_savings']} ({res['comparison']['savings_percent']}%)")
    print(f"CO2 Emissions Avoided:      {res['comparison']['co2_saved_kg']} kg")
    print("=" * 60)
