from pydantic import BaseModel, conint


class CuttingParameters(BaseModel):
    kerf: conint(ge=0) = 0
    top_trim: conint(ge=0) = 0
    bottom_trim: conint(ge=0) = 0
    left_trim: conint(ge=0) = 0
    right_trim: conint(ge=0) = 0
