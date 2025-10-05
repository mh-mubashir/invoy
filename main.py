from fastapi import FastAPI
from src.calendar.routes import router as calendar_router

app = FastAPI(title="Google Calendar Integration API")

# Register routes
app.include_router(calendar_router, prefix="", tags=["Calendar"])

@app.get("/")
def root():
    return {"message": "Google Calendar API Backend is running!"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI Google Calendar Backend...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
