from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.calendar.routes import router as calendar_router

app = FastAPI()
templates = Jinja2Templates(directory="pages")

app = FastAPI(title="Google Calendar Integration API")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routes
app.include_router(calendar_router, prefix="", tags=["Calendar"])

# Example route to render the login page
@app.get("/", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI Google Calendar Backend...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
