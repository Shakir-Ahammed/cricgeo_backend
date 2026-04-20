"""
Profile schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class ProfileOut(BaseModel):
    id: int
    user_id: int
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    gender: Optional[int] = None          # 1=male, 2=female, 3=other
    date_of_birth: Optional[date] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlayerRoleOut(BaseModel):
    id: int
    user_id: int
    role: int   # 1=batsman,2=bowler,3=wicketkeeper,4=allrounder
    created_at: datetime

    class Config:
        from_attributes = True


class PlayerRoleRequest(BaseModel):
    role: int = Field(..., ge=1, le=4, description="1=batsman,2=bowler,3=wicketkeeper,4=allrounder")


class BattingInfoOut(BaseModel):
    id: int
    user_id: int
    batting_style: Optional[int] = None   # 1=left, 2=right
    batting_order: Optional[int] = None   # 1=opening,2=middle,3=lower,4=tailender
    created_at: datetime

    class Config:
        from_attributes = True


class BattingInfoRequest(BaseModel):
    batting_style: Optional[int] = Field(None, ge=1, le=2, description="1=left, 2=right")
    batting_order: Optional[int] = Field(None, ge=1, le=4, description="1=opening,2=middle,3=lower,4=tailender")


class BowlingInfoOut(BaseModel):
    id: int
    user_id: int
    bowling_style: Optional[int] = None    # 1=left-arm, 2=right-arm
    bowling_category: Optional[int] = None # 1=pace, 2=spin
    bowling_type: Optional[int] = None     # 1-7
    created_at: datetime

    class Config:
        from_attributes = True


class BowlingInfoRequest(BaseModel):
    bowling_style: Optional[int] = Field(None, ge=1, le=2, description="1=left-arm,2=right-arm")
    bowling_category: Optional[int] = Field(None, ge=1, le=2, description="1=pace,2=spin")
    bowling_type: Optional[int] = Field(None, ge=1, le=7, description="1=fast..7=wrist spin")
