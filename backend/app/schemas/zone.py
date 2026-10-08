from pydantic import BaseModel


class ZoneOut(BaseModel):
    h3_id: str
    total_drivers: int
    available_drivers: int  # supply
    open_requests: int  # demand
    demand_supply_ratio: float  # raw ratio; the surge engine (Batch B) smooths it