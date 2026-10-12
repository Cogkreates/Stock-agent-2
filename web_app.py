from flask import Flask, jsonify, render_template, request
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/status")
def status():
    return jsonify({
        "ready": (ROOT / "run_demo.py").exists(),
        "project": "Stock Agent",
        "mode": "demo supplier simulation"
    })

@app.post("/api/run")
def run_agent():
    payload = request.get_json(silent=True) or {}
    recovery = bool(payload.get("recovery", True))
    env = os.environ.copy()
    env["STOCK_RECOVERY"] = "on" if recovery else "off"

    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "run_demo.py")],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        output = (proc.stdout or "")
        if proc.stderr:
            # Keep stderr visible for debugging but avoid dumping enormous traces.
            output += "\n\n[stderr]\n" + proc.stderr[-5000:]

        spent_match = re.search(r"Spent\s+([0-9.]+)\s+of\s+([0-9.]+)\s*\|\s*remaining:\s*(\{.*\})", output)
        spent = float(spent_match.group(1)) if spent_match else None
        budget = float(spent_match.group(2)) if spent_match else 300.0

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        events = []
        for line in lines:
            # The agent's own log format is the source of truth for the activity feed.
            if any(tag in line for tag in ("SKIP", "ADJUST", "HOLD", "RECOVER", "ALERT",
                                            "VERIFIED", "SHIPMENT", "approval requested", "NOTIFY")):
                events.append(line)

        return jsonify({
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "mode": "Recovery enabled" if recovery else "Baseline mode",
            "spent": spent,
            "budget": budget,
            "remaining": spent_match.group(3) if spent_match else None,
            "events": events,
            "log": output[-18000:],
            "message": "Agent run completed." if proc.returncode == 0 else "Agent run returned an error. Inspect the run log."
        }), (200 if proc.returncode == 0 else 500)
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "message": "The agent run exceeded 45 seconds. Try again.", "log": ""}), 504
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc), "log": ""}), 500

if __name__ == "__main__":
    if not (ROOT / "run_demo.py").exists():
        raise SystemExit("Place web_app.py in the same folder as run_demo.py, agent.py, models.py, mock_supplier.py, and tracing.py.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
