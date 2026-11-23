
from pydantic import BaseModel, ConfigDict


# -------------------------
# 태그 응답
# -------------------------

class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
