import os
import secrets
import logging
import time
from enum import Enum

from pydantic import BaseModel, Field
from fastapi import FastAPI, Security, HTTPException, status, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from colorhash import ColorHash
from moviepy import (
        ColorClip,
        TextClip,
        CompositeVideoClip,
)

logging.basicConfig(level=logging.INFO, format="time=%(asctime)s level=%(levelname)s msg=%(message)s")

class Month(str, Enum):
    JANUARY = "january"
    FEBRUARY = "february"
    MARCH = "march"
    APRIL = "april"
    MAY = "may"
    JUNE = "june"
    JULY = "july"
    AUGUST = "august"
    SEPTEMBER = "september"
    OCTOBER = "october"
    NOVEMBER = "november"
    DECEMBER = "december"

class CreateMonthlyPlaylistCover(BaseModel):
    """
    Represents the request body for creating a monthly playlist cover.
    """
    month: Month 
    year: int = Field(..., ge=2025, description="Year must be 2000 or later")
    playlist_id: str

class CreateWeeklyPlaylistCover(BaseModel):
    """
    Represents the request body for creating a monthly playlist cover.
    """
    week: int = Field(..., ge=1, le=52, description="Week must be between 1 and 52 (inclusive)")
    year: int = Field(..., ge=2025, description="Year must be 2000 or later")
    playlist_id: str


API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY environment variable is not set")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(
        provided_key: str = Security(api_key_header)
):
    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )

    if not secrets.compare_digest(provided_key, API_KEY):
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key",
        )
    return provided_key


app = FastAPI()

@app.middleware("http")
async def log_request(request: Request, call_next):
    logging.info(f"Processing request: {request.method} {request.url}")
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    logging.info(f"Request '{request.method} {request.url}' processed in {process_time:.4f} seconds")
    return response

@app.post("/playlist/monthly", dependencies=[Depends(get_api_key)])
async def read_root(playlist: CreateMonthlyPlaylistCover):
    size = (600, 600)
    text = f"{playlist.month.value} {playlist.year}"
    c = ColorHash(text)
    bg = ColorClip(size=size, color=c.rgb)

    # 2) Black rectangle spanning ~90% width and ~15% height
    rect_w = int(bg.w * 0.9)
    rect_h = int(bg.h * 0.15)
    margin = 20  # distance from edges

    # place it a bit above & left of the bottom-right corner
    x_pos = bg.w - rect_w
    y_pos = bg.h - rect_h - margin
    rect = (
        ColorClip(size=(rect_w, rect_h), color=(0, 0, 0)).with_position((x_pos, y_pos))
    )

    font_path = os.getenv("FONT_PATH")
    if not font_path:
        logging.error("FONT_PATH environment variable is not set")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 3) Text centered in that rectangle
    txt = (
        TextClip(text=text, font_size=60, color="white", font=font_path, size=(None, rect_h))
    )
    # center it by offsetting half the rectangle minus half the text
    txt = txt.with_position((x_pos + 20, y_pos))

    # 4) Composite and save one frame
    final = CompositeVideoClip([bg, rect, txt])
    final.save_frame("june.png")

    return {"url": "image_url" }

