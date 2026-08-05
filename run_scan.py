"""Agente de escaneo. SOLO AVISA: no ejecuta ordenes (deliberado).

Ejemplos:
  python run_scan.py --tickers "USDJPY=X" "EURUSD=X" --tf 1d --period 5y
  python run_scan.py --tickers "USDJPY=X" --tf 1h --period 720d --no-res
  python run_scan.py --tickers "USDJPY=X" --backtest --period max
  python run_scan.py --tickers "USDJPY=X" --loop 3600 --capital 10000 --risk-pct 0.5

Alertas Telegram (opcional): exporta TG_TOKEN y TG_CHAT antes de ejecutar.
"""
import argparse
import json
import time
import urllib.parse
import urllib.request
import os

import pandas as pd

from config import Params
from detector import find_signals
from backtest import backtest, resumen


def fetch(ticker: str, tf: str, period: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(ticker, interval=tf, period=period,
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close"]].dropna()


def telegram(msg: str) -> None:
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not tok or not chat:
        return
    url = (f"https://api.telegram.org/bot{tok}/sendMessage?"
           + urllib.parse.urlencode({"chat_id": chat, "text": msg}))
    try:
        urllib.request.urlopen(url, timeout=10)
    except Exception as e:
        print(f"(aviso Telegram fallido: {e})")


def sizing(risk_price: float, capital: float, risk_pct: float) -> str:
    money = capital * risk_pct / 100.0
    units = money / risk_price
    return (f"  tamano por riesgo {risk_pct}% de {capital:,.0f}: "
            f"{units:,.0f} unidades (~{units/100000:.2f} lotes FX). "
            f"Ojo: en pares XXX/JPY el riesgo esta en JPY.")


def scan_once(args, P: Params, seen: set) -> None:
    for tk in args.tickers:
        try:
            df = fetch(tk, args.tf, args.period)
        except Exception as e:
            print(f"[{tk}] error de datos: {e}")
            continue
        if df.empty:
            print(f"[{tk}] sin datos.")
            continue
        sigs = find_signals(df, P, tk)
        if args.backtest:
            trades = backtest(df, sigs, P)
            print(f"\n===== BACKTEST {tk} ({args.tf}, {args.period}) =====")
            print(resumen(trades))
            if not trades.empty:
                print(trades.to_string(index=False))
            continue
        fresh = [s for s in sigs
                 if (tk, str(s.date)) not in seen and s.i >= len(df) - args.recent]
        for s in fresh:
            seen.add((tk, str(s.date)))
            msg = s.describe()
            if args.capital:
                msg += "\n" + sizing(s.risk, args.capital, args.risk_pct)
            print("\n" + msg)
            telegram(msg)
        if not fresh:
            print(f"[{tk}] sin senal nueva ({len(sigs)} historicas en el periodo).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+",
                    default=["USDJPY=X", "EURUSD=X", "GBPUSD=X", "^GSPC"])
    ap.add_argument("--tf", default="1d", choices=["1d", "1h"])
    ap.add_argument("--period", default="5y",
                    help="p.ej. 2y, 5y, max (1h: maximo ~720d)")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--loop", type=int, default=0,
                    help="segundos entre escaneos (0 = una sola vez)")
    ap.add_argument("--recent", type=int, default=3,
                    help="solo avisa de senales en las ultimas N barras")
    ap.add_argument("--capital", type=float, default=0)
    ap.add_argument("--risk-pct", type=float, default=0.5)
    ap.add_argument("--no-res", action="store_true",
                    help="desactiva la condicion de resistencia (para 1h)")
    ap.add_argument("--no-ma", action="store_true")
    ap.add_argument("--test-alert", action="store_true",
                    help="envia un mensaje de prueba a Telegram y sale")
    args = ap.parse_args()

    if args.test_alert:
        if not os.environ.get("TG_TOKEN") or not os.environ.get("TG_CHAT"):
            print("FALTA configurar TG_TOKEN y TG_CHAT (secretos).")
            return
        msg = ("Prueba OK: agente 'pauta plana' conectado. "
               "Los avisos de senales llegaran a este chat.")
        print(msg)
        telegram(msg)
        return

    P = Params()
    if args.no_res:
        P.require_res = False
    if args.no_ma:
        P.require_ma = False
    if args.tf == "1h" and args.period == "5y":
        args.period = "720d"

    seen: set = set()
    while True:
        scan_once(args, P, seen)
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
