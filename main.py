from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.calendar.routes import router as calendar_router

app = FastAPI()
templates = Jinja2Templates(directory="pages")

app = FastAPI(title="Google Calendar Integration API")

# Register routes
app.include_router(calendar_router, prefix="", tags=["Calendar"])

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI Google Calendar Backend...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
