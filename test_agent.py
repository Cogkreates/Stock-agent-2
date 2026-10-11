import unittest

from agent import StockAgent
from mock_supplier import MockSupplier
from models import WantItem


class TestStockAgent(unittest.TestCase):
    def make_agent(self, wantlist, script, approval_threshold=50.0, budget=300.0):
        notifications = []
        agent = StockAgent(
            MockSupplier(script),
            wantlist,
            budget=budget,
            approval_threshold=approval_threshold,
            approve_fn=lambda item, qty, cost: True,
            notify_fn=lambda msg: notifications.append(msg),
        )
        return agent, notifications

    def test_sold_out_substitution(self):
        want = WantItem("ceramic mug", max_price=6.00, qty=12, alternatives=["stoneware mug"])
        agent, notifications = self.make_agent(
            [want],
            {
                1: [
                    {"type": "new_stock", "item": {"sku": "MUG-1", "name": "Ceramic Mug", "price": 5.50, "stock": 50}},
                    {"type": "sell_out_on_order", "sku": "MUG-1"},
                    {"type": "new_stock", "item": {"sku": "MUG-2", "name": "Stoneware Mug", "price": 5.80, "stock": 30}},
                ]
            },
        )

        agent.run_tick()

        self.assertEqual(agent.remaining["ceramic mug"], 0)
        self.assertGreater(agent.spent, 0.0)
        self.assertTrue(any("substituting approved alternative" in entry for entry in agent.log))
        self.assertEqual(len(notifications), 0)

    def test_price_ceiling_alert(self):
        want = WantItem("tote bag", max_price=3.00, qty=30)
        agent, notifications = self.make_agent(
            [want],
            {1: [{"type": "new_stock", "item": {"sku": "BAG-1", "name": "Tote Bag", "price": 4.50, "stock": 200}}]},
        )

        agent.run_tick()

        self.assertEqual(agent.spent, 0.0)
        self.assertEqual(agent.remaining["tote bag"], 30)
        self.assertEqual(notifications, ["BAG-1: price 4.50 is over ceiling 3.00"])

    def test_payment_retry(self):
        want = WantItem("led bulb", max_price=2.50, qty=40)
        agent, notifications = self.make_agent(
            [want],
            {1: [
                {"type": "new_stock", "item": {"sku": "LED-1", "name": "LED Bulb 9W", "price": 2.00, "stock": 300}},
                {"type": "decline_payment"},
            ]},
        )

        agent.run_tick()

        self.assertEqual(agent.spent, 80.0)
        self.assertEqual(agent.remaining["led bulb"], 0)
        self.assertNotIn("payment declined twice, needs user", "\n".join(agent.log))
        self.assertEqual(notifications, [])


if __name__ == "__main__":
    unittest.main()
