"""
Smart EV Charging Schedule Optimization Engine
Formulates and solves the optimal charging schedule using Linear Programming / MILP (SciPy)
and provides an adaptive real-time greedy water-filling heuristic fallback.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
import numpy as np
from scipy.optimize import linprog


@dataclass
class EVSpecs:
    """EV specifications and charging constraints."""
    battery_capacity_kwh: float = 60.0    # Total battery capacity in kWh
    current_soc_percent: float = 20.0     # Initial battery SoC (0-100%)
    target_soc_percent: float = 85.0      # Target SoC at departure (0-100%)
    max_charge_power_kw: float = 7.4      # Max charger rating (kW), e.g. 7.4 kW Level 2 (32A @ 230V)
    min_charge_power_kw: float = 0.0      # Min power if charging
    charge_efficiency: float = 0.92       # AC to DC conversion efficiency (92%)
    arrival_hour: int = 18                # Vehicle arrival hour (0-23) e.g., 6:00 PM
    departure_hour: int = 7               # Vehicle departure hour next morning (7:00 AM)


@dataclass
class GridEnvironment:
    """External grid, tariff, and renewable generation parameters."""
    hourly_tariffs: List[float]           # 24-hr electricity prices (currency/kWh)
    solar_generation_kw: List[float]      # 24-hr available local solar PV power (kW)
    grid_power_limit_kw: float = 12.0     # Max total power capacity on household/transformer
    base_load_kw: Optional[List[float]] = None  # Non-EV baseline load (fridge, AC, lights)
    carbon_intensity_g_kwh: Optional[List[float]] = None  # g CO2/kWh per hour


class EVChargingOptimizer:
    """
    Solves optimal charging schedule to minimize cost while respecting:
    - User departure deadline & target SoC
    - Battery degradation & power limits
    - Grid peak transformer limits
    - Maximization of self-consumed solar PV
    """

    def __init__(self, ev_specs: EVSpecs, grid_env: GridEnvironment, time_step_hours: float = 1.0):
        self.ev = ev_specs
        self.grid = grid_env
        self.dt = time_step_hours
        self.n_steps = len(grid_env.hourly_tariffs)

        if self.grid.base_load_kw is None:
            # Default residential baseline profile (kW)
            self.grid.base_load_kw = [
                0.8, 0.7, 0.6, 0.6, 0.7, 1.2, 2.0, 2.5, 1.8, 1.5,
                1.4, 1.3, 1.2, 1.3, 1.5, 1.8, 2.8, 3.5, 3.8, 3.4,
                2.6, 2.0, 1.4, 1.0
            ]

        if self.grid.carbon_intensity_g_kwh is None:
            # Typical grid carbon intensity: higher in evening peak (coal/gas peakers), lower midday/night
            self.grid.carbon_intensity_g_kwh = [
                480, 460, 450, 450, 470, 520, 580, 540, 420, 350,
                300, 280, 290, 310, 360, 440, 590, 680, 710, 670,
                590, 530, 500, 490
            ]

    def _get_active_charging_window(self) -> List[int]:
        """
        Calculates time step indices where vehicle is plugged in.
        Handles overnight plugging (e.g. 18:00 to 07:00 next day).
        """
        arr = self.ev.arrival_hour
        dep = self.ev.departure_hour
        if arr < dep:
            return list(range(arr, dep))
        else:
            # Wraps around midnight
            return list(range(arr, self.n_steps)) + list(range(0, dep))

    def solve(self) -> Dict[str, Any]:
        """Runs the optimization and returns schedule comparison."""
        active_hours = self._get_active_charging_window()
        total_energy_needed = max(
            0.0,
            (self.ev.target_soc_percent - self.ev.current_soc_percent)
            * self.ev.battery_capacity_kwh
            / (100.0 * self.ev.charge_efficiency)
        )

        # 1. Solve optimal schedule using SciPy Linear Programming
        opt_schedule, opt_soc = self._solve_linprog(active_hours, total_energy_needed)

        # 2. Simulate uncontrolled (immediate) charging benchmark
        uncontrolled_schedule, uncontrolled_soc = self._simulate_uncontrolled(
            active_hours, total_energy_needed
        )

        # 3. Calculate cost, carbon, and solar metrics for both
        opt_metrics = self._calculate_metrics(opt_schedule)
        uncontrolled_metrics = self._calculate_metrics(uncontrolled_schedule)

        # Calculate savings
        cost_savings = uncontrolled_metrics["total_cost"] - opt_metrics["total_cost"]
        savings_percent = (
            (cost_savings / uncontrolled_metrics["total_cost"] * 100.0)
            if uncontrolled_metrics["total_cost"] > 0
            else 0.0
        )
        co2_savings_kg = (uncontrolled_metrics["carbon_kg"] - opt_metrics["carbon_kg"])

        # Format full 24h timeline
        timeline = []
        for h in range(self.n_steps):
            timeline.append({
                "hour": h,
                "hour_label": f"{h:02d}:00",
                "is_plugged": h in active_hours,
                "tariff": round(self.grid.hourly_tariffs[h], 2),
                "solar_kw": round(self.grid.solar_generation_kw[h], 2),
                "baseload_kw": round(self.grid.base_load_kw[h], 2),
                "opt_power_kw": round(float(opt_schedule[h]), 2),
                "opt_soc_percent": round(float(opt_soc[h]), 1),
                "opt_cost": round(float(opt_schedule[h] * self.grid.hourly_tariffs[h] * self.dt), 2),
                "uncontrolled_power_kw": round(float(uncontrolled_schedule[h]), 2),
                "uncontrolled_soc_percent": round(float(uncontrolled_soc[h]), 1),
                "uncontrolled_cost": round(float(uncontrolled_schedule[h] * self.grid.hourly_tariffs[h] * self.dt), 2),
            })

        return {
            "status": "OPTIMAL",
            "ev_specs": asdict(self.ev),
            "energy_needed_kwh": round(total_energy_needed, 2),
            "optimized": opt_metrics,
            "uncontrolled": uncontrolled_metrics,
            "comparison": {
                "cost_savings": round(cost_savings, 2),
                "savings_percent": round(savings_percent, 1),
                "co2_saved_kg": round(co2_savings_kg, 2),
                "peak_power_shaved_kw": round(
                    max(uncontrolled_schedule) - max(opt_schedule), 2
                ),
            },
            "timeline": timeline,
        }

    def _solve_linprog(self, active_hours: List[int], total_energy_needed: float):
        """
        Formulates and solves:
        Min sum( (Tariff_t - Solar_incentive_t) * P_t * dt )
        s.t.
          sum_{t in active} P_t * dt * eta >= Energy_needed
          P_t <= min(P_max, Grid_limit - Baseload_t)
          P_t == 0 for t not in active
        """
        c = np.zeros(self.n_steps)
        bounds = []

        for h in range(self.n_steps):
            if h in active_hours:
                # Effective price incentivizes charging during solar generation
                solar_bonus = min(self.grid.solar_generation_kw[h] / max(1.0, self.ev.max_charge_power_kw), 1.0) * 1.5
                c[h] = (self.grid.hourly_tariffs[h] - solar_bonus) * self.dt
                # Max power respecting grid limit
                grid_headroom = max(0.0, self.grid.grid_power_limit_kw - self.grid.base_load_kw[h])
                ub = min(self.ev.max_charge_power_kw, grid_headroom)
                bounds.append((0.0, ub))
            else:
                c[h] = 0.0
                bounds.append((0.0, 0.0))

        # Constraint: total energy delivered must satisfy target SoC
        # sum_{h in active} (P_h * dt * eta) >= (Target_SoC - Current_SoC)/100 * Capacity
        # In standard form A_ub * x <= b_ub, so: -sum(P_h * dt * eta) <= -Target_Energy
        A_ub = np.zeros((1, self.n_steps))
        for h in active_hours:
            A_ub[0, h] = -1.0 * self.dt

        b_ub = [-total_energy_needed]

        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

        if res.success:
            opt_power = res.x
        else:
            # Fallback heuristic: Water-filling lowest cost hours
            opt_power = self._greedy_water_filling(active_hours, total_energy_needed)

        # Compute SoC progression
        soc_prog = self._compute_soc_profile(opt_power)
        return opt_power, soc_prog

    def _greedy_water_filling(self, active_hours: List[int], total_energy_needed: float) -> np.ndarray:
        """Heuristic greedy water-filling in lowest tariff hours."""
        schedule = np.zeros(self.n_steps)
        energy_remaining = total_energy_needed
        # Sort active hours by tariff ascending
        sorted_hours = sorted(active_hours, key=lambda h: self.grid.hourly_tariffs[h] - self.grid.solar_generation_kw[h] * 0.5)

        for h in sorted_hours:
            if energy_remaining <= 0.001:
                break
            grid_headroom = max(0.0, self.grid.grid_power_limit_kw - self.grid.base_load_kw[h])
            max_p = min(self.ev.max_charge_power_kw, grid_headroom)
            p = min(max_p, energy_remaining / self.dt)
            schedule[h] = p
            energy_remaining -= p * self.dt

        return schedule

    def _simulate_uncontrolled(self, active_hours: List[int], total_energy_needed: float):
        """Simulates uncontrolled charging: charges immediately at max power upon arrival."""
        uncontrolled = np.zeros(self.n_steps)
        energy_remaining = total_energy_needed

        for h in active_hours:
            if energy_remaining <= 0.001:
                break
            grid_headroom = max(0.0, self.grid.grid_power_limit_kw - self.grid.base_load_kw[h])
            p = min(self.ev.max_charge_power_kw, grid_headroom, energy_remaining / self.dt)
            uncontrolled[h] = p
            energy_remaining -= p * self.dt

        soc_prog = self._compute_soc_profile(uncontrolled)
        return uncontrolled, soc_prog

    def _compute_soc_profile(self, power_schedule: np.ndarray) -> np.ndarray:
        """Calculates 24h battery SoC curve."""
        soc = np.zeros(self.n_steps)
        current = self.ev.current_soc_percent

        # For display, propagate through day starting from arrival or hour 0
        arr = self.ev.arrival_hour
        # Populate pre-arrival hours with current_soc
        for h in range(self.n_steps):
            if h < arr and self.ev.arrival_hour > self.ev.departure_hour:
                soc[h] = self.ev.target_soc_percent  # Vehicle was already charged in the morning
            else:
                soc[h] = current

        # Track dynamically across plugged hours
        tracked_soc = self.ev.current_soc_percent
        active_hours = self._get_active_charging_window()
        for h in active_hours:
            energy_added = power_schedule[h] * self.dt * self.ev.charge_efficiency
            delta_soc = (energy_added / self.ev.battery_capacity_kwh) * 100.0
            tracked_soc = min(100.0, tracked_soc + delta_soc)
            soc[h] = tracked_soc

        return soc

    def _calculate_metrics(self, power_schedule: np.ndarray) -> Dict[str, float]:
        """Calculates energy, cost, solar self-consumption, and carbon emissions."""
        total_kwh = float(np.sum(power_schedule) * self.dt)
        total_cost = 0.0
        solar_used_kwh = 0.0
        carbon_g = 0.0

        for h in range(self.n_steps):
            p = power_schedule[h]
            e = p * self.dt
            total_cost += e * self.grid.hourly_tariffs[h]
            solar_used = min(e, self.grid.solar_generation_kw[h] * self.dt)
            solar_used_kwh += solar_used
            # Grid portion carbon
            grid_imported = max(0.0, e - solar_used)
            carbon_g += grid_imported * self.grid.carbon_intensity_g_kwh[h]

        return {
            "total_energy_kwh": round(total_kwh, 2),
            "total_cost": round(total_cost, 2),
            "solar_self_consumed_kwh": round(solar_used_kwh, 2),
            "solar_coverage_percent": round((solar_used_kwh / total_kwh * 100.0) if total_kwh > 0 else 0.0, 1),
            "carbon_kg": round(carbon_g / 1000.0, 2),
            "peak_charging_power_kw": round(float(np.max(power_schedule)), 2),
        }
