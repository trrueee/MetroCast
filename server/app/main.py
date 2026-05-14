from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="MetroCast API", description="Daily Subway Podcast MVP API")

# Add CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to MetroCast API"}

@app.post("/pipeline/run")
async def run_pipeline():
    # In a real app, this would be a background task
    from jobs.daily_pipeline import DailyPipeline
    pipeline = DailyPipeline()
    result = pipeline.run()
    if not result:
        raise HTTPException(status_code=500, detail="Pipeline failed")
    return result

@app.get("/episodes")
async def get_episodes():
    # Mock for now
    return [
        {
            "id": 1,
            "title": "5月13日 AI 通勤早报",
            "description": "今天聊三个 AI 行业动态...",
            "audio_url": "/storage/episode_20260513.mp3",
            "created_at": "2026-05-13T07:00:00"
        }
    ]

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
