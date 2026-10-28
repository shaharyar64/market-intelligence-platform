from pydantic import BaseModel
from typing import List


class BanksFilterResponse(BaseModel):
    banks: List[str]


class ProductsFilterResponse(BaseModel):
    products: List[str]


class AssociationsFilterResponse(BaseModel):
    associations: List[str]
