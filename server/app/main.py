import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from storage.registry import load_registry, get_episode, find_episode_dir

app = FastAPI(title="小站早班车 API", description="Daily Subway Podcast API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated audio files directly
if os.path.isdir("storage"):
    app.mount("/storage", StaticFiles(directory="storage"), name="storage")


@app.get("/")
async def root():
    return {"message": "小站早班车 API", "version": "0.2.0"}


@app.post("/pipeline/run")
async def run_pipeline(mode: str = "news", topic: str = None):
    from jobs.daily_pipeline import DailyPipeline
    pipeline = DailyPipeline()
    result = pipeline.run(mode=mode, topic=topic)
    if not result:
        raise HTTPException(status_code=500, detail="Pipeline failed")
    return result


@app.get("/episodes")
async def list_episodes():
    """Return all generated episodes (newest first, summary only)."""
    registry = load_registry()
    return registry


@app.get("/episodes/{episode_id}")
async def get_episode_detail(episode_id: str):
    """Return full episode metadata including segments and sources."""
    ep_dir = find_episode_dir(episode_id)
    if not ep_dir:
        raise HTTPException(status_code=404, detail="Episode not found")

    ep_json_path = os.path.join(ep_dir, "episode.json")
    if not os.path.isfile(ep_json_path):
        raise HTTPException(status_code=404, detail="Episode metadata not found")

    with open(ep_json_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/episodes/{episode_id}/audio")
async def get_episode_audio(episode_id: str):
    """Serve the MP3 audio file for an episode."""
    ep_dir = find_episode_dir(episode_id)
    if not ep_dir:
        raise HTTPException(status_code=404, detail="Episode not found")

    audio_path = os.path.join(ep_dir, "final.mp3")
    if not os.path.isfile(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"{episode_id}.mp3",
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
