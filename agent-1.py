from mock_supplier import SoldOut, PriceChanged, PaymentDeclined
from tracing import traced, log as trace_log


class StockAgent:
    def __init__(self, supplier, wantlist, budget, approval_threshold,
                 approve_fn, notify_fn, recovery=True):
        self.supplier = supplier
        self.wantlist = wantlist
        self.budget = budget
        self.approval_threshold = approval_threshold   # orders above this need a human OK
        self.approve_fn = approve_fn
        self.notify_fn = notify_fn
        self.recovery = recovery       # False = baseline run: no substitution, no retry
        self.remaining = {w.name: w.qty for w in wantlist}
        self.spent = 0.0
        self.open_orders = {}          # order_id -> last known shipment stage
        self.log = []

    # ---- main loop -------------------------------------------------
    @traced("CHAIN", name="run_tick")
    def run_tick(self):
        for item in self.supplier.tick():
            self.handle_item(item)
        self.track_shipments()

    # ---- decide ----------------------------------------------------
    @traced("AGENT", name="handle_item", role="buyer",
            goal="order wanted stock within price ceiling and budget")
    def handle_item(self, item):
        want = next((w for w in self.wantlist if w.name in item.name.lower()), None)
        if want is None:
            return self._log("SKIP", item.sku, "not on want-list")
        self.try_order(want, item, allow_sub=True)

    @traced("CHAIN", name="try_order")
    def try_order(self, want, item, allow_sub):
        qty = self.remaining[want.name]
        if qty <= 0:
            return
        if item.price > want.max_price:
            return self._alert(item.sku, f"price {item.price:.2f} is over ceiling {want.max_price:.2f}")

        if self.spent + qty * item.price > self.budget:      # fit the budget
            qty = int((self.budget - self.spent) // item.price)
            if qty <= 0:
                return self._alert(item.sku, "budget exhausted")
            self._log("ADJUST", item.sku, f"reduced qty to {qty} to fit budget")

        cost = qty * item.price
        if cost > self.approval_threshold and not self.approve_fn(item, qty, cost):
            return self._log("HOLD", item.sku, f"{cost:.2f} not approved by user")

        for attempt in (1, 2):                               # one retry on payment failure
            try:
                oid = self.supplier.place_order(item.sku, qty, want.max_price)
                break
            except SoldOut:
                if not self.recovery:
                    return self._alert(item.sku, "sold out, recovery disabled")
                self._log("RECOVER", item.sku, "sold out during checkout")
                return self.substitute(want, item.sku) if allow_sub else self._alert(item.sku, "sold out")
            except PriceChanged as e:
                return self._alert(item.sku, f"price changed to {e.new_price:.2f}, not ordering")
            except PaymentDeclined:
                if not self.recovery:
                    return self._alert(item.sku, "payment declined, recovery disabled")
                self._log("RECOVER", item.sku, f"payment declined (attempt {attempt})")
                if attempt == 2:
                    return self._alert(item.sku, "payment declined twice, needs user")
        self.verify(want, item, qty, oid)

    def substitute(self, want, failed_sku):
        for alt in self.supplier.catalog.values():
            if (alt.sku != failed_sku and alt.stock > 0 and alt.price <= want.max_price
                    and any(a in alt.name.lower() for a in want.alternatives)):
                self._log("RECOVER", alt.sku, f"substituting approved alternative '{alt.name}'")
                return self.try_order(want, alt, allow_sub=False)
        self._alert(failed_sku, "no approved substitute in stock")

    # ---- verify ----------------------------------------------------
    @traced("GUARDRAIL", name="verify_order")
    def verify(self, want, item, qty, oid):
        conf = self.supplier.get_confirmation(oid)
        ok = (conf["status"] == "CONFIRMED" and conf["qty"] == qty
              and conf["unit_price"] <= want.max_price)
        if not ok:
            return self._alert(item.sku, f"{oid} could not be verified, marked unconfirmed")
        self.spent += qty * conf["unit_price"]
        self.remaining[want.name] -= qty
        self.open_orders[oid] = "ORDERED"
        self._log("VERIFIED", item.sku, f"{oid}: {qty} x {conf['unit_price']:.2f} confirmed")

    # ---- track + notify -------------------------------------------
    @traced("CHAIN", name="track_shipments")
    def track_shipments(self):
        for oid, last in list(self.open_orders.items()):
            stage = self.supplier.shipment_status(oid)
            if stage == last:
                continue
            self.open_orders[oid] = stage
            self._log("SHIPMENT", oid, stage)
            if stage == "ARRIVED":
                self.notify_fn(f"{oid} has arrived. Pickup details go to waiting customers.")
                del self.open_orders[oid]

    # ---- helpers ---------------------------------------------------
    def _log(self, kind, ref, msg):
        line = f"[tick {self.supplier.tick_no}] {kind:<8} {ref}: {msg}"
        self.log.append(line)
        print(line)
        trace_log(kind.lower(), level="warning" if kind in ("ALERT", "RECOVER") else "info",
                  ref=ref, detail=msg, tick=self.supplier.tick_no)

    def _alert(self, ref, msg):
        self._log("ALERT", ref, msg)
        self.notify_fn(f"{ref}: {msg}")
