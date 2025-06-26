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
from minio import Minio

S3_URL = os.getenv("S3_URL", "")
IMAGE_SIZE = (600, 600)

client = Minio(
    S3_URL,
    os.getenv("S3_ACCESS_KEY", ""),
    os.getenv("S3_SECRET_KEY")
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

class CreateWeeklyPlaylistCover(BaseModel):
    """
    Represents the request body for creating a monthly playlist cover.
    """
    year1: int = Field(ge=2025, description="Year must be 2025 or later")
    month1: Month
    day1: int = Field(ge=1, le=31, description="Day must be between 1 and 31")

    year2: int = Field(ge=2025, description="Year must be 2025 or later")
    month2: Month
    day2: int = Field(ge=1, le=31, description="Day must be between 1 and 31")

DEFAULT_IMAGE_DIR = "/tmp"
PLAYLIST_COVER_BUCKET = "playlist-covers"

API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY", "")

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

def _generate_monthly_image(text: str, name: str) -> str:
    """Generates an image with a colored background and text plaque."""
    # get font path
    font_path = os.getenv("FONT_PATH")
    if not font_path:
        logging.debug("FONT_PATH environment variable is not set, using default font")

    # generate color
    c = ColorHash(text)
    bg = ColorClip(size=IMAGE_SIZE, color=c.rgb)

    # text plaque at the bottom right
    rect_w = int(bg.w * 0.9)
    rect_h = int(bg.h * 0.15)
    margin = 20  # distance from edges

    # place it a bit above & left of the bottom-right corner
    x_pos = bg.w - rect_w
    y_pos = bg.h - rect_h - margin
    rect = (
        ColorClip(size=(rect_w, rect_h), color=(0, 0, 0)).with_position((x_pos, y_pos))
    )

    # create text clip
    txt = (
        TextClip(text=text, font_size=60, color="white", font=font_path, size=(None, rect_h))
    )
    # position it within rectangle
    txt = txt.with_position((x_pos + 20, y_pos))

    # composite and save one frame
    dest = os.path.join(os.getenv("IMAGE_DIR", DEFAULT_IMAGE_DIR), name)
    final = CompositeVideoClip([bg, rect, txt])
    final.save_frame(dest)
    return dest

def _format_weekly_date(month: Month, day: int, year: int) -> str:
    return f"{(list(Month).index(month) + 1):02d}/{day:02d}/{year}"

def _generate_weekly_image(month1: Month, day1: int, year1: int, month2: Month, day2: int, year2: int) -> str:
    # get font path
    font_path = os.getenv("FONT_PATH")
    if not font_path:
        logging.debug("FONT_PATH environment variable is not set, using default font")

    # generate color
    date1, date2 = _format_weekly_date(month1, day1, year1), _format_weekly_date(month2, day2, year2)
    c = ColorHash(f"{date1} {date2}")
    bg = ColorClip(size=IMAGE_SIZE, color=c.rgb)

    # text plaque at the bottom right
    rect_w = int(bg.w * 0.9)
    rect_h = int(bg.h * 0.15)
    margin = 20  # distance from edges

    # top left rectangle
    x_pos = 0
    y_pos = margin
    rect1 = (
        ColorClip(size=(rect_w, rect_h), color=(0, 0, 0)).with_position((x_pos, y_pos))
    )

    # create text clip
    date1txt = (
        TextClip(text=date1, font_size=60, color="white", font=font_path, size=(None, rect_h))
    )
    date1txt = date1txt.with_position((x_pos + margin, y_pos))

    # bottom right rectangle
    x_pos = bg.w - rect_w
    y_pos = bg.h - rect_h - margin
    rect2 = (
        ColorClip(size=(rect_w, rect_h), color=(0, 0, 0)).with_position((x_pos, y_pos))
    )
    date2txt = (
        TextClip(text=date2, font_size=60, color="white", font=font_path, size=(None, rect_h))
    )
    date2txt = date2txt.with_position((x_pos + margin, y_pos))

    # compile image
    dest = os.path.join(os.getenv("IMAGE_DIR", DEFAULT_IMAGE_DIR), f"{date1.replace('/', '-')}-{date2.replace('/', '-')}.png")
    final = CompositeVideoClip([bg, rect1, date1txt, rect2, date2txt])
    final.save_frame(dest)
    return dest

app = FastAPI()

@app.middleware("http")
async def log_request(request: Request, call_next):
    logging.info(f"Processing request: {request.method} {request.url}")
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    logging.info(f"Request '{request.method} {request.url}' processed in {process_time:.4f} seconds")
    return response

@app.post("/monthly-playlist", dependencies=[Depends(get_api_key)])
async def create_monthly_playlist_cover(playlist: CreateMonthlyPlaylistCover):
    logging.info("Generating image")
    name= f"{playlist.month.value}_{playlist.year}.png"
    path = _generate_monthly_image(
        text=f"{playlist.month.value} {playlist.year}",
        name=name,
    )
    logging.info("Uploading image to S3")
    object_name = f"monthly/{playlist.year}/{playlist.month.value}.png"
    with open(path, 'rb') as file_data:
        client.put_object(
            bucket_name=PLAYLIST_COVER_BUCKET,
            object_name=object_name,
            data=file_data,
            length=os.path.getsize(path),
        )

    return {"url": f"https://{S3_URL}/{PLAYLIST_COVER_BUCKET}/{object_name}" }

@app.post("/weekly-playlist", dependencies=[Depends(get_api_key)])
async def create_weekly_playlist_cover(playlist: CreateWeeklyPlaylistCover):
    logging.info("Generating image")
    path = _generate_weekly_image(playlist.month1, playlist.day1, playlist.year1, playlist.month2, playlist.day2, playlist.year2)

    logging.info("Uploading image to S3")
    object_name = f"weekly/{playlist.year2}/{playlist.month2.value}/{playlist.month1.value}_{playlist.day1}-{playlist.month2.value}_{playlist.day2}.png"
    with open(path, 'rb') as file_data:
        client.put_object(
            bucket_name=PLAYLIST_COVER_BUCKET,
            object_name=object_name,
            data=file_data,
            length=os.path.getsize(path),
        )

    return {"url": f"https://{S3_URL}/{PLAYLIST_COVER_BUCKET}/{object_name}" }
