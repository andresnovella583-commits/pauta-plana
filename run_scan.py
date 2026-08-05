name: pauta-plana
run-name: pauta-plana (${{ inputs.modo || 'scan automatico' }})
on:
  schedule:
    - cron: "15 * * * 1-5"
  workflow_dispatch:
    inputs:
      modo:
        description: "Que ejecutar"
        type: choice
        default: scan
        options: [scan, backtest, prueba]
permissions:
  contents: read
jobs:
  agente:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - name: Prueba de aviso
        if: ${{ inputs.modo == 'prueba' }}
        env:
          TG_TOKEN: ${{ secrets.TG_TOKEN }}
          TG_CHAT: ${{ secrets.TG_CHAT }}
        run: python run_scan.py --test-alert
      - name: Backtest (leer el resultado en este log)
        if: ${{ inputs.modo == 'backtest' }}
        run: python run_scan.py --tickers "USDJPY=X" "EURUSD=X" "GBPUSD=X" "^GSPC" "^NDX" --tf 1d --period max --backtest
      - name: Escaneo diario
        if: ${{ github.event_name == 'schedule' || inputs.modo == 'scan' }}
        env:
          TG_TOKEN: ${{ secrets.TG_TOKEN }}
          TG_CHAT: ${{ secrets.TG_CHAT }}
        run: python run_scan.py --tickers "USDJPY=X" "EURUSD=X" "GBPUSD=X" "^GSPC" "^NDX" --tf 1d --period 5y --recent 2
      - name: Escaneo 1 hora (pauta plana intradia)
        if: ${{ github.event_name == 'schedule' || inputs.modo == 'scan' }}
        env:
          TG_TOKEN: ${{ secrets.TG_TOKEN }}
          TG_CHAT: ${{ secrets.TG_CHAT }}
        run: python run_scan.py --tickers "USDJPY=X" "EURUSD=X" "GBPUSD=X"
