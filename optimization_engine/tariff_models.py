"""
Tariff Models for Smart EV Charging Optimization
Provides standard Time-of-Use (TOU), Critical Peak, and Dynamic Real-Time Pricing models.
"""

from typing import Dict, List, Optional
import numpy as np


class TariffModel:
    """Base class for electricity tariff models."""
    def __init__(self, name: str, currency: str = "₹", unit: str = "kWh"):
        self.name = name
        self.currency = currency
        self.unit = unit

    def get_hourly_rates(self) -> List[float]:
        """Returns 24-hour rate array in currency/kWh."""
        raise NotImplementedError


class StandardTOUTariff(TariffModel):
    """
    Standard 3-Tier Time-of-Use Tariff:
    - Off-Peak (00:00 - 06:00, 23:00 - 24:00): Low rate (excess baseload)
    - Shoulder / Normal (06:00 - 17:00, 21:00 - 23:00): Moderate rate
    - Peak (17:00 - 21:00): High rate (evening residential peak)
    """
    def __init__(
        self,
        off_peak_rate: float = 3.50,
        shoulder_rate: float = 6.20,
        peak_rate: float = 11.80,
        currency: str = "₹"
    ):
        super().__init__(name="3-Tier Time-of-Use (TOU)", currency=currency)
        self.off_peak = off_peak_rate
        self.shoulder = shoulder_rate
        self.peak = peak_rate

    def get_hourly_rates(self) -> List[float]:
        rates = []
        for hour in range(24):
            if 0 <= hour < 6 or hour >= 23:
                rates.append(self.off_peak)
            elif 17 <= hour < 21:
                rates.append(self.peak)
            else:
                rates.append(self.shoulder)
        return rates

    def get_tier_name(self, hour: int) -> str:
        if 0 <= hour < 6 or hour >= 23:
            return "Off-Peak"
        elif 17 <= hour < 21:
            return "Peak"
        return "Shoulder"


class SolarIncentiveTariff(TariffModel):
    """
    Solar-Friendly Super Off-Peak Tariff (e.g., California Duck Curve / Solar Curtailment):
    - Super Off-Peak / Solar Sponge (10:00 - 15:00): Lowest rate to encourage absorbing solar
    - Off-Peak (00:00 - 06:00, 22:00 - 24:00): Low rate
    - Shoulder (06:00 - 10:00, 15:00 - 17:00, 21:00 - 22:00): Normal rate
    - Peak (17:00 - 21:00): Maximum rate
    """
    def __init__(
        self,
        solar_sponge_rate: float = 2.80,
        off_peak_rate: float = 4.20,
        shoulder_rate: float = 7.00,
        peak_rate: float = 13.50,
        currency: str = "₹"
    ):
        super().__init__(name="Solar-Friendly TOU (Duck Curve)", currency=currency)
        self.solar_sponge = solar_sponge_rate
        self.off_peak = off_peak_rate
        self.shoulder = shoulder_rate
        self.peak = peak_rate

    def get_hourly_rates(self) -> List[float]:
        rates = []
        for hour in range(24):
            if 10 <= hour < 15:
                rates.append(self.solar_sponge)
            elif 0 <= hour < 6 or hour >= 22:
                rates.append(self.off_peak)
            elif 17 <= hour < 21:
                rates.append(self.peak)
            else:
                rates.append(self.shoulder)
        return rates


class DynamicRealTimeTariff(TariffModel):
    """
    Simulated dynamic wholesale day-ahead spot market price with stochastic volatility.
    """
    def __init__(self, base_price: float = 5.0, seed: Optional[int] = 42, currency: str = "₹"):
        super().__init__(name="Dynamic Real-Time Spot Tariff", currency=currency)
        self.base_price = base_price
        self.seed = seed

    def get_hourly_rates(self) -> List[float]:
        rng = np.random.default_rng(self.seed)
        hours = np.arange(24)
        # Diurnal pattern with morning and evening bumps
        diurnal = 3.0 * np.sin((hours - 8) * np.pi / 12) ** 2 + 5.0 * np.exp(-((hours - 19) ** 2) / 6)
        noise = rng.normal(0, 0.4, 24)
        rates = np.clip(self.base_price + diurnal + noise, 1.5, 20.0)
        return [round(float(r), 2) for r in rates]


AVAILABLE_TARIFFS = {
    "standard_tou": StandardTOUTariff(),
    "solar_tou": SolarIncentiveTariff(),
    "dynamic_spot": DynamicRealTimeTariff()
}
