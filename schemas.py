from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime, date

# =========================
# TODAY PRICE RESPONSE
# =========================

class GoldPriceResponse(BaseModel):
    city: str
    date: date
    prices: Dict[str, float]   # {"24K": 13724, "22K": 12580, "18K": 10490}
    currency: str
    last_updated: datetime


# =========================
# HISTORY RESPONSE
# =========================

class GoldHistoryItem(BaseModel):
    date: date
    price: float


class GoldHistoryResponse(BaseModel):
    city: str
    karat: str                # "24K" | "22K" | "18K"
    currency: str
    days: int
    history: List[GoldHistoryItem]


# =========================
# REBUILD MODELS
# =========================

GoldPriceResponse.model_rebuild()
GoldHistoryItem.model_rebuild()
GoldHistoryResponse.model_rebuild()
