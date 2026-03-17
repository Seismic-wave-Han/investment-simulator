from __future__ import annotations

import math

import pandas as pd


def annual_to_monthly_rate(annual_return_pct: float) -> float:
    r = annual_return_pct / 100.0
    return math.pow(1.0 + r, 1.0 / 12.0) - 1.0


def nominal_to_real_return_pct(*, nominal_return_pct: float, inflation_pct: float) -> float:
    """
    Fisher exact:
      1+r_real = (1+r_nominal)/(1+inflation)
    """
    r_n = nominal_return_pct / 100.0
    pi = inflation_pct / 100.0
    if pi <= -1.0:
        return float("nan")
    return ((1.0 + r_n) / (1.0 + pi) - 1.0) * 100.0


def months_to_years_months(months: int) -> tuple[int, int]:
    if months <= 0:
        return 0, 0
    return months // 12, months % 12


def required_monthly_saving(seed: float, monthly_r: float, target: float, months: int) -> float:
    if months <= 0:
        return float("nan")
    if target <= seed:
        return 0.0
    if monthly_r == 0.0:
        return (target - seed) / months

    a = math.pow(1.0 + monthly_r, months)
    annuity_factor = (a - 1.0) / monthly_r
    return (target - seed * a) / annuity_factor


def months_to_reach_target(seed: float, monthly_saving: float, monthly_r: float, target: float) -> int | None:
    if target <= seed:
        return 0
    if monthly_saving < 0.0:
        return None
    if monthly_saving == 0.0:
        if seed <= 0.0:
            return None
        if monthly_r <= 0.0:
            return None
        return math.ceil(math.log(target / seed) / math.log(1.0 + monthly_r))
    if monthly_r == 0.0:
        return math.ceil((target - seed) / monthly_saving)

    k = monthly_saving / monthly_r
    denom = seed + k
    if denom <= 0:
        return None
    ratio = (target + k) / denom
    if ratio <= 1.0:
        return 0
    return math.ceil(math.log(ratio) / math.log(1.0 + monthly_r))


def required_annual_return_pct_no_saving(*, seed: float, target: float, years: int) -> float | None:
    """
    월저축 없이(=0) seed가 years년 뒤 target이 되기 위한 연 수익률(%)을 역산합니다.
    연복리 기준: target = seed * (1+r)^years
    """
    if years <= 0:
        return None
    if target <= seed:
        return 0.0
    if seed <= 0.0:
        return None
    r = math.pow(target / seed, 1.0 / years) - 1.0
    return r * 100.0


def simulate_months_until_target(
    *,
    seed_eok: float,
    monthly_saving_eok: float,
    annual_return_pct: float,
    inflation_pct: float,
    return_basis: str,
    target_kind: str,
    target_eok: float,
    max_years: int = 80,
) -> int | None:
    infl = inflation_pct / 100.0
    max_months = int(max_years) * 12

    if return_basis == "nominal":
        monthly_r = annual_to_monthly_rate(annual_return_pct)
        nominal = float(seed_eok)
        for m in range(0, max_months + 1):
            if m != 0:
                nominal = nominal * (1.0 + monthly_r) + monthly_saving_eok

            if target_kind.startswith("명목"):
                if nominal >= target_eok:
                    return m
            else:
                real_now = nominal / ((1.0 + infl) ** (m / 12.0)) if infl > -1.0 else float("nan")
                if real_now >= target_eok:
                    return m
        return None

    monthly_real_r = annual_to_monthly_rate(annual_return_pct)
    real = float(seed_eok)
    for m in range(0, max_months + 1):
        if m != 0:
            real = real * (1.0 + monthly_real_r) + monthly_saving_eok

        if target_kind.startswith("실질"):
            if real >= target_eok:
                return m
        else:
            nominal_now = real * ((1.0 + infl) ** (m / 12.0)) if infl > -1.0 else float("nan")
            if nominal_now >= target_eok:
                return m
    return None


def simulate_yearly_table(
    *,
    seed_eok: float,
    monthly_saving_eok: float,
    annual_return_pct: float,
    inflation_pct: float,
    years: int,
    return_basis: str,
) -> pd.DataFrame:
    infl = inflation_pct / 100.0
    monthly_contrib = monthly_saving_eok

    rows: list[dict[str, float | int]] = []
    nominal_value = float(seed_eok)
    real_value = float(seed_eok)
    total_contrib = float(seed_eok)

    for n in range(1, years + 1):
        if return_basis == "nominal":
            monthly_r = annual_to_monthly_rate(annual_return_pct)
            for _ in range(12):
                nominal_value = nominal_value * (1.0 + monthly_r) + monthly_contrib
                total_contrib += monthly_contrib
            real_value = nominal_value / ((1.0 + infl) ** n) if infl > -1.0 else float("nan")
        else:
            monthly_real_r = annual_to_monthly_rate(annual_return_pct)
            for _ in range(12):
                real_value = real_value * (1.0 + monthly_real_r) + monthly_contrib
                total_contrib += monthly_contrib
            nominal_value = real_value * ((1.0 + infl) ** n) if infl > -1.0 else float("nan")

        rows.append(
            {
                "년": n,
                "누적 납입(억)": total_contrib,
                "명목 총자산(억)": nominal_value,
                "실질 총자산(억, 현재가치)": real_value,
            }
        )

    return pd.DataFrame(rows)

