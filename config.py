"""Parámetros del detector de 'pauta plana' bajista (vídeo OPLA / J.L. Cava).

Etiquetas de origen:
  [LIBRO]       -> número explícito en 'Sistemas de Especulación', p.323
  [VIDEO]       -> mencionado en el vídeo, pero SIN umbral concreto
  [MI ELECCION] -> decisión mía porque el vídeo no lo define.
                   Cambiar estos valores cambia las señales.
"""
from dataclasses import dataclass


@dataclass
class Params:
    # ---------- pivotes ----------
    pivot_k: int = 3            # [MI ELECCION] barras a cada lado para confirmar pivote

    # ---------- directriz alcista ----------
    trend_look: int = 160       # [MI ELECCION] ventana hacia atras para buscar minimos
    trend_min_lows: int = 3     # [VIDEO implicito] minimos crecientes necesarios
    trend_use_lows: int = 3     # [MI ELECCION] usa los N ultimos minimos (directriz reciente)
    trend_tol_atr: float = 0.9  # [MI ELECCION] tolerancia de los minimos respecto a la linea
    line_break_atr: float = 0.10  # [MI ELECCION] margen para dar la directriz por rota

    # ---------- figura de techo (dos maximos crecientes + valle) ----------
    top_leg_min_atr: float = 1.5  # [MI ELECCION] tamano minimo de la pierna de ruptura
    leg_max_bars: int = 45        # [MI ELECCION] la ruptura no puede ser antigua
    viol_atr: float = 1.1         # [VIDEO 'perforacion violenta'; umbral MI ELECCION]

    # ---------- resistencia relevante a la izquierda ----------
    res_look: int = 500         # [VIDEO 'maximos 2024-25'; ventana MI ELECCION]
    res_excl: int = 25          # excluye las barras mas recientes
    res_min_hist: int = 120     # historia minima para poder evaluar la condicion
    res_tol_atr: float = 2.0    # [MI ELECCION] cuanto puede quedarse por debajo el techo
    res_over_atr: float = 3.0   # [VIDEO 'la supera brevemente'; tope MI ELECCION]
    require_res: bool = True    # en 1h con poca historia, ponlo en False y valida en diario

    # ---------- sentimiento (PROXY: el '60%' del video no es computable) ----------
    sent_sma: int = 50          # [MI ELECCION] precio > SMA50 y SMA50 subiendo
    sent_slope_bars: int = 10
    require_sent: bool = True

    # ---------- pauta plana: LOS UNICOS NUMEROS DEL LIBRO ----------
    b_lo: float = 0.81          # [LIBRO] onda B normal: 81%-100% de A
    b_hi: float = 1.00          # [LIBRO]
    c_lo: float = 1.00          # [LIBRO] onda C: 100%-138.2% de B
    c_hi: float = 1.382         # [LIBRO]
    ratio_tol: float = 0.06     # [MI ELECCION] tolerancia sobre los ratios

    # ---------- zona de medias en el techo de C ----------
    ma_fast: int = 21           # [VIDEO se contradice: '20/21 y 50' vs '9 y 21']
    ma_slow: int = 50
    ma_tol_atr: float = 0.8     # [MI ELECCION]
    require_ma: bool = True

    # ---------- disparo (giro a la baja tras la onda C) ----------
    turn_within: int = 6        # [MI ELECCION] barras max tras el techo de C
    stop_buf_atr: float = 0.2   # [VIDEO 'stop muy ajustado'; buffer MI ELECCION]

    # ---------- gestion / backtest ----------
    rr: float = 2.0             # [VIDEO 'me vale con 1:2 o 1:3']
    max_hold: int = 40          # [MI ELECCION] barras maximas en posicion
    spread: float = 0.02        # coste ida+vuelta en unidades de precio (USDJPY ~2 pips)
    carry_per_bar: float = 0.0  # coste de financiacion por barra (ver README: corto USDJPY paga)
    atr_n: int = 14
