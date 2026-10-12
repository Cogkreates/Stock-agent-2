from models import WantItem
from mock_supplier import MockSupplier
from agent import StockAgent
import os
import tracing

# STOCK_RECOVERY=off runs the BASELINE (no substitution, no retry) for before/after traces
RECOVERY = os.environ.get("STOCK_RECOVERY", "on").lower() != "off"
tracing.init(workflow_name="stock-agent" if RECOVERY else "stock-agent-baseline")

WANTLIST = [
    WantItem("usb-c cable", max_price=4.00, qty=20),
    WantItem("ceramic mug", max_price=6.00, qty=12, alternatives=["stoneware mug"]),
    WantItem("tote bag", max_price=3.00, qty=30),
    WantItem("led bulb", max_price=2.50, qty=40),
]

SCRIPT = {
    1: [{"type": "new_stock", "item": dict(sku="CAB-1", name="USB-C Cable 1m", price=3.20, stock=100)},
        {"type": "new_stock", "item": dict(sku="NTB-1", name="Notebook A5", price=1.10, stock=500)}],   # happy path + skip
    2: [{"type": "new_stock", "item": dict(sku="MUG-1", name="Ceramic Mug", price=5.50, stock=50)},
        {"type": "sell_out_on_order", "sku": "MUG-1"},                                                   # race: sells out
        {"type": "new_stock", "item": dict(sku="MUG-2", name="Stoneware Mug", price=5.80, stock=30)}],
    3: [{"type": "new_stock", "item": dict(sku="BAG-1", name="Tote Bag", price=4.50, stock=200)}],      # over price ceiling
    4: [{"type": "new_stock", "item": dict(sku="LED-1", name="LED Bulb 9W", price=2.00, stock=300)},
        {"type": "decline_payment"}],                                                                    # payment fails once
}


def approve(item, qty, cost):
    print(f"           >> approval requested: {qty} x {item.name} = {cost:.2f} (auto-approved in demo)")
    return True


agent = StockAgent(MockSupplier(SCRIPT), WANTLIST, budget=300.0, approval_threshold=50.0,
                   approve_fn=approve, notify_fn=lambda m: print(f"           >> NOTIFY: {m}"),
                   recovery=RECOVERY)


@tracing.traced("WORKFLOW", name="stock_agent_run" if RECOVERY else "stock_agent_baseline_run")
def run(ticks=7):
    for _ in range(ticks):
        agent.run_tick()
    return {"mode": "recovery" if RECOVERY else "baseline",
            "spent": round(agent.spent, 2), "remaining": dict(agent.remaining)}


summary = run()
tracing.shutdown()
print(f"\nSpent {agent.spent:.2f} of 300.00 | remaining: {agent.remaining}")
