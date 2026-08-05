"""Backtest de las senales: entrada en la apertura siguiente, salida por
stop / objetivo rr / tiempo. Pesimista: si stop y objetivo se tocan en la
misma barra, cuenta el stop. Descuenta spread y carry por barra mantenida.
"""
import numpy as np
import pandas as pd

from config import Params
from detector import Signal


def backtest(df: pd.DataFrame, sigs: list, P: Params) -> pd.DataFrame:
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    rows = []
    for sg in sigs:
        t = sg.i
        if t + 1 >= len(df):
            continue
        entry = o[t + 1]
        risk = sg.stop - entry
        if risk <= 0:
            continue
        target = entry - P.rr * risk
        gross, held, outcome = None, 0, "timeout"
        for j in range(t + 1, min(t + 1 + P.max_hold, len(df))):
            held = j - t
            if h[j] >= sg.stop:
                gross, outcome = -1.0, "stop"
                break
            if l[j] <= target:
                gross, outcome = P.rr, "objetivo"
                break
        if gross is None:
            j = min(t + P.max_hold, len(df) - 1)
            gross = (entry - c[j]) / risk
        cost = (P.spread + P.carry_per_bar * held) / risk
        rows.append({
            "fecha": df.index[t], "ticker": sg.ticker, "entrada": entry,
            "stop": sg.stop, "riesgo": risk, "barras": held,
            "resultado": outcome, "R_bruto": gross,
            "coste_R": cost, "R_neto": gross - cost,
        })
    return pd.DataFrame(rows)


def resumen(trades: pd.DataFrame) -> str:
    if trades.empty:
        return "Sin operaciones en el periodo analizado."
    n = len(trades)
    wins = (trades["R_neto"] > 0).sum()
    pos = trades.loc[trades["R_neto"] > 0, "R_neto"].sum()
    neg = -trades.loc[trades["R_neto"] <= 0, "R_neto"].sum()
    pf = pos / neg if neg > 0 else float("inf")
    txt = (
        f"operaciones: {n}   aciertos: {wins} ({100*wins/n:.0f}%)\n"
        f"expectancy neta: {trades['R_neto'].mean():+.2f} R/trade   "
        f"total: {trades['R_neto'].sum():+.1f} R   profit factor: {pf:.2f}\n"
        f"coste medio (spread+carry): {trades['coste_R'].mean():.2f} R/trade"
    )
    if n < 30:
        txt += f"\nAVISO: n={n} < 30 -> SIN validez estadistica. No operes con esto."
    return txt
