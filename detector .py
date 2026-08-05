"""Detector de la 'pauta plana' de continuacion bajista.

Secuencia que busca (sobre UNA serie OHLC):
  1) Tendencia alcista con directriz sobre minimos crecientes (pendiente > 0).
  2) Figura de techo: dos maximos crecientes P1 < P2 y perforacion del valle
     entre ambos, con 'violencia' (rango >= viol_atr * ATR).
  3) Perforacion de la directriz alcista.
  4) P2 formado en zona de resistencia historica relevante (maximos antiguos).
  5) Sentimiento alcista previo (PROXY: precio > SMA50 y SMA50 subiendo).
  6) Tras la pierna bajista, pauta plana correctiva al alza A-B-C con los
     ratios del libro: B = 81-100% de A, C = 100-138.2% de B, y techo de C
     en la banda de medias (21/50).
  7) Disparo: barra de giro bajista poco despues del techo de C.
Salida: senal con entrada de referencia, stop (techo de C + buffer) y
objetivos 2R/3R, mas el detalle de cada condicion.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from config import Params


# ---------------------------------------------------------------- indicadores
def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).mean().to_numpy()


def atr(h, l, c, n) -> np.ndarray:
    cp = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - cp), np.abs(l - cp)))
    return pd.Series(tr).rolling(n).mean().to_numpy()


def pivots(h, l, k):
    """Indices de pivotes (maximos/minimos locales confirmados con k barras)."""
    n = len(h)
    ph = np.zeros(n, dtype=bool)
    pl = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        if h[i] >= h[i - k:i + k + 1].max() and h[i] > h[i - k:i].max():
            ph[i] = True
        if l[i] <= l[i - k:i + k + 1].min() and l[i] < l[i - k:i].min():
            pl[i] = True
    return np.where(ph)[0], np.where(pl)[0]


def fit_directriz(l, pl_idx, b, P: Params, atr_b: float):
    """Recta sobre los ultimos minimos pivotados antes de la barra b."""
    lows = pl_idx[(pl_idx >= b - P.trend_look) & (pl_idx < b)]
    if len(lows) < P.trend_min_lows:
        return None
    lows = lows[-P.trend_use_lows:]
    x = lows.astype(float)
    y = l[lows]
    slope, inter = np.polyfit(x, y, 1)
    resid = y - (slope * x + inter)
    if resid.min() < -P.trend_tol_atr * atr_b:
        return None
    return slope, inter


# ------------------------------------------------------------------- senal
@dataclass
class Signal:
    ticker: str
    i: int
    date: object
    entry: float
    stop: float
    risk: float
    target2: float
    target3: float
    rB: float
    rC: float
    p2_i: int
    p2_date: object
    conds: dict = field(default_factory=dict)

    def describe(self) -> str:
        marks = "  ".join(f"{'OK ' if v else 'NO '}{k}" for k, v in self.conds.items())
        return (
            f"[{self.ticker}] SENAL CORTA  {self.date}\n"
            f"  techo P2: {self.p2_date}   rB={self.rB:.2f}  rC={self.rC:.2f}\n"
            f"  entrada ref: {self.entry:.4f}   stop: {self.stop:.4f}"
            f"   riesgo: {self.risk:.4f}\n"
            f"  objetivo 1:2 = {self.target2:.4f}   objetivo 1:3 = {self.target3:.4f}\n"
            f"  condiciones: {marks}"
        )


# ---------------------------------------------------------------- detector
def find_signals(df: pd.DataFrame, P: Params, ticker: str = "") -> list:
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    n = len(df)
    if n < max(P.sent_sma, P.ma_slow) + 30:
        return []

    A = atr(h, l, c, P.atr_n)
    f = sma(c, P.ma_fast)
    s = sma(c, P.ma_slow)
    s50 = sma(c, P.sent_sma)
    ph_idx, pl_idx = pivots(h, l, P.pivot_k)

    warm = max(P.sent_sma, P.ma_slow, P.atr_n) + P.pivot_k + 2
    sigs, used_tops = [], set()

    for t in range(warm, n):
        # -- barra de giro bajista
        if not (c[t] < o[t] and c[t] < l[t - 1]):
            continue

        # -- techo de la onda C: ultimo pivote alto confirmado y reciente
        cs = ph_idx[(ph_idx <= t - P.pivot_k) & (ph_idx >= t - P.turn_within)]
        if len(cs) == 0:
            continue
        ci = int(cs[-1])
        Ch = h[ci]
        if np.isnan(A[t]) or np.isnan(A[ci]):
            continue
        if h[ci + 1:t + 1].max() > Ch + 0.1 * A[t]:   # C invalidada
            continue

        # -- estructura A-B-C hacia atras
        bls = pl_idx[pl_idx < ci]
        if len(bls) == 0:
            continue
        bi = int(bls[-1]); Bl = l[bi]
        ahs = ph_idx[ph_idx < bi]
        if len(ahs) == 0:
            continue
        ai = int(ahs[-1]); Ah = h[ai]
        l0s = pl_idx[pl_idx < ai]
        if len(l0s) == 0:
            continue
        zi = int(l0s[-1]); L0 = l[zi]

        Alen, Blen = Ah - L0, Ah - Bl
        if Alen <= 0 or Blen <= 0:
            continue
        rB = Blen / Alen
        rC = (Ch - Bl) / Blen
        if not (P.b_lo - P.ratio_tol <= rB <= P.b_hi + P.ratio_tol):
            continue
        if not (P.c_lo - P.ratio_tol <= rC <= P.c_hi + P.ratio_tol):
            continue
        if c[t] <= Bl:            # estructura ya rota: llegamos tarde
            continue

        # -- figura de techo antes de la pierna bajista
        p2s = ph_idx[ph_idx < zi]
        if len(p2s) < 2:
            continue
        p2, p1 = int(p2s[-1]), int(p2s[-2])
        if np.isnan(A[p2]) or h[p2] <= h[p1]:
            continue
        if zi - p2 > P.leg_max_bars:
            continue
        if (h[p2] - L0) < P.top_leg_min_atr * A[p2]:
            continue
        V = l[p1:p2 + 1].min()
        if L0 >= V:               # la pierna debe haber perforado el valle
            continue
        below = np.where(c[p2 + 1:zi + 1] < V)[0]
        if len(below) == 0:
            continue
        b = p2 + 1 + below[0]
        if np.isnan(A[b]):
            continue

        conds = {"techo_2max": True, "pauta_plana_ratios": True}
        conds["C_bajo_P2"] = Ch < h[p2]
        conds["perforacion_violenta"] = (
            (h[b] - l[b]) >= P.viol_atr * A[b] or (V - c[b]) >= 0.25 * A[b]
        )

        line = fit_directriz(l, pl_idx, b, P, A[b])
        if line is None:
            conds["directriz_rota"] = False
        else:
            slope, inter = line
            broke = any(
                c[j] < slope * j + inter - P.line_break_atr * A[j]
                for j in range(b, min(b + 4, zi + 1))
                if not np.isnan(A[j])
            )
            conds["directriz_rota"] = bool(slope > 0 and broke)

        lo_i, hi_i = max(0, p2 - P.res_look), p2 - P.res_excl
        if hi_i - lo_i >= P.res_min_hist:
            hh = h[lo_i:hi_i].max()
            conds["resistencia_relevante"] = bool(
                hh - P.res_tol_atr * A[p2] <= h[p2] <= hh + P.res_over_atr * A[p2]
            )
        else:
            conds["resistencia_relevante"] = False  # sin historia no se puede afirmar

        conds["sentimiento_proxy"] = bool(
            not np.isnan(s50[p2])
            and c[p2] > s50[p2]
            and s50[p2] > s50[p2 - P.sent_slope_bars]
        )

        if np.isnan(f[ci]) or np.isnan(s[ci]):
            conds["giro_en_zona_medias"] = False
        else:
            lo_b = min(f[ci], s[ci]) - P.ma_tol_atr * A[ci]
            hi_b = max(f[ci], s[ci]) + P.ma_tol_atr * A[ci]
            conds["giro_en_zona_medias"] = bool(lo_b <= Ch <= hi_b)

        required = ["techo_2max", "pauta_plana_ratios", "C_bajo_P2",
                    "perforacion_violenta", "directriz_rota"]
        if P.require_res:
            required.append("resistencia_relevante")
        if P.require_sent:
            required.append("sentimiento_proxy")
        if P.require_ma:
            required.append("giro_en_zona_medias")
        if not all(conds[k] for k in required):
            continue
        if p2 in used_tops:
            continue
        used_tops.add(p2)

        stop = Ch + P.stop_buf_atr * A[t]
        entry = c[t]
        risk = stop - entry
        if risk <= 0:
            continue
        sigs.append(Signal(
            ticker=ticker, i=t, date=df.index[t], entry=entry, stop=stop,
            risk=risk, target2=entry - 2 * risk, target3=entry - 3 * risk,
            rB=rB, rC=rC, p2_i=p2, p2_date=df.index[p2], conds=conds,
        ))
    return sigs


# ------------------------------------------------- diagnostico de embudo
def funnel(df: pd.DataFrame, P: Params) -> dict:
    """Cuenta cuantos candidatos sobreviven cada filtro, en orden.
    Sirve para ver DONDE muere la estrategia antes de relajar nada."""
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    n = len(df)
    A = atr(h, l, c, P.atr_n)
    f = sma(c, P.ma_fast)
    s = sma(c, P.ma_slow)
    s50 = sma(c, P.sent_sma)
    ph_idx, pl_idx = pivots(h, l, P.pivot_k)

    keys = ["1_techo_doble_y_ruptura_valle", "2_mas_violencia",
            "3_mas_directriz_rota", "4_mas_resistencia_relevante",
            "5_mas_sentimiento_proxy", "6_mas_plana_ABC_ratios",
            "7_mas_C_en_zona_medias", "8_mas_barra_de_giro_SENAL"]
    cnt = {k: 0 for k in keys}

    for idx in range(1, len(ph_idx)):
        p1, p2 = int(ph_idx[idx - 1]), int(ph_idx[idx])
        if h[p2] <= h[p1] or np.isnan(A[p2]):
            continue
        V = l[p1:p2 + 1].min()
        end = min(p2 + 1 + P.leg_max_bars, n)
        below = np.where(c[p2 + 1:end] < V)[0]
        if len(below) == 0:
            continue
        b = p2 + 1 + below[0]
        if np.isnan(A[b]):
            continue
        cnt[keys[0]] += 1

        if not ((h[b] - l[b]) >= P.viol_atr * A[b]
                or (V - c[b]) >= 0.25 * A[b]):
            continue
        cnt[keys[1]] += 1

        line = fit_directriz(l, pl_idx, b, P, A[b])
        dir_ok = False
        if line is not None:
            slope, inter = line
            dir_ok = slope > 0 and any(
                c[j] < slope * j + inter - P.line_break_atr * A[j]
                for j in range(b, min(b + 4, n)) if not np.isnan(A[j])
            )
        if not dir_ok:
            continue
        cnt[keys[2]] += 1

        lo_i, hi_i = max(0, p2 - P.res_look), p2 - P.res_excl
        res_ok = False
        if hi_i - lo_i >= P.res_min_hist:
            hh = h[lo_i:hi_i].max()
            res_ok = (hh - P.res_tol_atr * A[p2] <= h[p2]
                      <= hh + P.res_over_atr * A[p2])
        if P.require_res and not res_ok:
            continue
        cnt[keys[3]] += 1

        sent_ok = (p2 - P.sent_slope_bars >= 0
                   and not np.isnan(s50[p2]) and c[p2] > s50[p2]
                   and s50[p2] > s50[p2 - P.sent_slope_bars])
        if P.require_sent and not sent_ok:
            continue
        cnt[keys[4]] += 1

        # pauta plana A-B-C dentro de las 60 barras tras la ruptura
        abc = None
        for zi in pl_idx[(pl_idx > b) & (pl_idx <= b + 60)]:
            zi = int(zi)
            if l[zi] >= V:
                continue
            for ai in ph_idx[(ph_idx > zi) & (ph_idx <= b + 60)][:2]:
                ai = int(ai)
                bls = pl_idx[(pl_idx > ai) & (pl_idx <= b + 60)]
                if len(bls) == 0:
                    continue
                bi = int(bls[0])
                chs = ph_idx[(ph_idx > bi)
                             & (ph_idx <= b + 60 + P.turn_within)]
                if len(chs) == 0:
                    continue
                ci = int(chs[0])
                Alen, Blen = h[ai] - l[zi], h[ai] - l[bi]
                if Alen <= 0 or Blen <= 0:
                    continue
                rB = Blen / Alen
                rC = (h[ci] - l[bi]) / Blen
                if (P.b_lo - P.ratio_tol <= rB <= P.b_hi + P.ratio_tol
                        and P.c_lo - P.ratio_tol <= rC <= P.c_hi + P.ratio_tol
                        and h[ci] < h[p2]):
                    abc = (zi, ai, bi, ci)
                    break
            if abc:
                break
        if not abc:
            continue
        cnt[keys[5]] += 1
        zi, ai, bi, ci = abc

        ma_ok = (not np.isnan(f[ci]) and not np.isnan(s[ci])
                 and min(f[ci], s[ci]) - P.ma_tol_atr * A[ci] <= h[ci]
                 <= max(f[ci], s[ci]) + P.ma_tol_atr * A[ci])
        if P.require_ma and not ma_ok:
            continue
        cnt[keys[6]] += 1

        trig = False
        for t in range(ci + P.pivot_k, min(ci + P.turn_within + 1, n)):
            if h[ci + 1:t + 1].max() > h[ci] + 0.1 * A[t]:
                break
            if c[t] < o[t] and c[t] < l[t - 1] and c[t] > l[bi]:
                trig = True
                break
        if trig:
            cnt[keys[7]] += 1
    return cnt
