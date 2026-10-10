from dataclasses import dataclass, field
from typing import List


@dataclass
class WantItem:
    name: str                 # keyword matched against catalog item names
    max_price: float          # per-unit price ceiling
    qty: int                  # total units wanted
    alternatives: List[str] = field(default_factory=list)  # approved substitutes (keywords)


@dataclass
class CatalogItem:
    sku: str
    name: str
    price: float
    stock: int
