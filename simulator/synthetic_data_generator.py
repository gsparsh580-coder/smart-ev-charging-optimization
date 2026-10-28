"""
Synthetic Data Generator for Smart EV Charging Optimization
Generates realistic 24-hour time-series datasets of EV arrivals, battery state-of-charge,
solar PV generation, grid baseload, dynamic electricity tariffs, and sensor readings.
"""

import os
from typing import Dict, Any, List
import numpy as np
import pandas as pd


class SyntheticDataGenerator:
    """
    Generates realistic synthetic datasets modeling residential EV charging profiles,
    rooftop solar PV generation, household base loads, and dynamic Time-of-Use tariffs.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def generate_24h_dataset(
        self,
        num_days: int = 7,
        time_step_mins: int = 15,
        battery_capacity_kwh: float = 60.0,
        max_charger_kw: float = 7.4
    ) -> pd.DataFrame:
        """Generates a multi-day time-series dataset at 15-minute or 60-minute resolution."""
        steps_per_day = int(1440 / time_step_mins)
        total_steps = num_days * steps_per_day
        records = []

        for step in range(total_steps):
            day_idx = step // steps_per_day
            step_of_day = step % steps_per_day
            hour_float = (step_of_day * time_step_mins) / 60.0
            hour = int(hour_float)
            minute = int((hour_float - hour) * 60)

            # 1. Dynamic Tariff Calculation (INR / kWh)
            # Peak: 17:00 - 21:00 (11.50), Off-Peak: 23:00 - 06:00 (3.50), Shoulder: 6.20
            if 0 <= hour < 6 or hour >= 23:
                base_tariff = 3.50
                tier = "Off-Peak"
            elif 17 <= hour < 21:
                base_tariff = 11.50
                tier = "Peak"
            else:
                base_tariff = 6.20
                tier = "Shoulder"
            tariff = round(base_tariff + self.rng.normal(0, 0.15), 2)

            # 2. Solar PV Generation (kW) - Bell curve between 06:30 and 18:30
            if 6.5 <= hour_float <= 18.5:
                solar_peak = 5.0 + self.rng.normal(0, 0.3)
                solar_kw = max(0.0, solar_peak * np.sin((hour_float - 6.5) * np.pi / 12) ** 2)
                # Occasional cloud drop
                if self.rng.random() < 0.15:
                    solar_kw *= self.rng.uniform(0.3, 0.7)
            else:
                solar_kw = 0.0
            solar_kw = round(float(solar_kw), 2)

            # 3. Household Base Load (kW)
            # Morning bump at 07:00 - 09:00, evening bump at 18:00 - 22:00
            morning_bump = 1.8 * np.exp(-((hour_float - 7.5) ** 2) / 2.0)
            evening_bump = 2.5 * np.exp(-((hour_float - 19.5) ** 2) / 3.0)
            base_kw = 0.7 + morning_bump + evening_bump + self.rng.normal(0, 0.1)
            base_kw = round(max(0.4, float(base_kw)), 2)

            # 4. EV Plugged Status & Natural Commuting Cycle
            # Arrives between 17:30 and 18:30, departs between 06:45 and 07:30
            is_plugged = (hour_float >= 18.0) or (hour_float < 7.0)

            records.append({
                "day": day_idx + 1,
                "step": step,
                "hour": hour,
                "minute": minute,
                "time_label": f"{hour:02d}:{minute:02d}",
                "tariff_inr_kwh": tariff,
                "tariff_tier": tier,
                "solar_generation_kw": solar_kw,
                "baseload_kw": base_kw,
                "ev_is_plugged": is_plugged,
                "grid_voltage_v": round(230.0 + self.rng.normal(0, 3.5), 1),
                "grid_frequency_hz": round(50.0 + self.rng.normal(0, 0.04), 2),
                "ambient_temp_c": round(26.0 + 8.0 * np.sin((hour_float - 8) * np.pi / 12) + self.rng.normal(0, 0.5), 1),
            })

        df = pd.DataFrame(records)
        return df

    def save_sample_csv(self, output_path: str = "data/synthetic_ev_dataset.csv") -> str:
        """Generates and saves a 7-day dataset as CSV."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df = self.generate_24h_dataset(num_days=7, time_step_mins=60)
        df.to_csv(output_path, index=False)
        return output_path


if __name__ == "__main__":
    gen = SyntheticDataGenerator()
    out = gen.save_sample_csv()
    print(f"Synthetic dataset generated and saved to: {out}")
