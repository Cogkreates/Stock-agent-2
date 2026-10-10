"""Deterministic fake supplier so demos and failure runs are repeatable.

Each tick() applies scripted events (new stock, price changes, sell-outs,
payment failures) so you can trigger recovery paths on demand.
"""
from models import CatalogItem
from tracing import traced

SHIPMENT_STAGES = ["ORDERED", "IN_TRANSIT", "AT_PORT", "ARRIVED"]


class SupplierError(Exception):
    pass


class SoldOut(SupplierError):
    pass


class PriceChanged(SupplierError):
    def __init__(self, new_price):
        super().__init__(f"price is now {new_price}")
        self.new_price = new_price


class PaymentDeclined(SupplierError):
    pass


class MockSupplier:
    def __init__(self, script):
        self.script = script          # {tick_number: [event, ...]}
        self.tick_no = 0
        self.catalog = {}             # sku -> CatalogItem
        self.orders = {}              # order_id -> dict
        self._fail_next = {}          # sku or "__payment__" -> exception
        self._n = 0

    def tick(self):
        """Advance time, apply events, return newly listed items."""
        self.tick_no += 1
        new = []
        for ev in self.script.get(self.tick_no, []):
            kind = ev["type"]
            if kind == "new_stock":
                item = CatalogItem(**ev["item"])
                self.catalog[item.sku] = item
                new.append(item)
            elif kind == "price_change":
                self.catalog[ev["sku"]].price = ev["price"]
            elif kind == "sell_out_on_order":      # item vanishes between detection and order
                self._fail_next[ev["sku"]] = SoldOut(ev["sku"])
            elif kind == "decline_payment":        # next order attempt fails once
                self._fail_next["__payment__"] = PaymentDeclined()
        return new

    @traced("TOOL", tool_name="place_order", description="Place an order with the supplier")
    def place_order(self, sku, qty, max_price):
        item = self.catalog.get(sku)
        if item is None:
            raise SoldOut(sku)
        if sku in self._fail_next:
            err = self._fail_next.pop(sku)
            item.stock = 0
            raise err
        if item.stock < qty:
            raise SoldOut(sku)
        if item.price > max_price:
            raise PriceChanged(item.price)
        if "__payment__" in self._fail_next:
            raise self._fail_next.pop("__payment__")
        item.stock -= qty
        self._n += 1
        oid = f"ORD-{self._n:04d}"
        self.orders[oid] = {"order_id": oid, "sku": sku, "qty": qty,
                            "unit_price": item.price, "status": "CONFIRMED",
                            "placed_tick": self.tick_no}
        return oid

    @traced("TOOL", tool_name="get_confirmation", description="Fetch the order confirmation")
    def get_confirmation(self, order_id):
        return dict(self.orders[order_id])

    @traced("TOOL", tool_name="shipment_status", description="Look up shipment stage")
    def shipment_status(self, order_id):
        waited = self.tick_no - self.orders[order_id]["placed_tick"]
        return SHIPMENT_STAGES[min(waited, len(SHIPMENT_STAGES) - 1)]
