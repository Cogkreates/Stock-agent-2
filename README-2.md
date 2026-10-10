# Stock Agent (neatHack)

Agent for traders: give it a want-list and a budget. It watches a supplier for new
non-perishable stock, orders automatically (with price ceilings, a budget cap and an
approval gate), verifies the confirmation, tracks the shipment, and notifies on arrival.

Run the demo: `python run_demo.py`

Layout: `mock_supplier.py` (scripted fake supplier), `agent.py` (watch, decide,
order, verify, recover, track), `tracing.py` (neatlogs tracing).

## Tracing with neatlogs

```
pip install -U neatlogs
export NEATLOGS_API_KEY="<project API key from app.neatlogs.com, Settings > API keys>"
python -m neatlogs doctor --local --json     # network-free check
python -m neatlogs doctor --probe --json     # sends a synthetic trace and reads it back
python run_demo.py                           # real run: one WORKFLOW trace, "stock-agent"
```

Never put the key in any file or commit it. Without the key or package, the demo runs untraced.
