# Invoy AI - Automated Invoice Generation

AI-powered invoice generation from Google Calendar or freeform text descriptions.

## Features

- **Calendar-based invoicing**: Fetch meetings from Google Calendar and auto-generate invoices
- **AI-assisted invoicing**: Describe work in natural language; Claude allocates hours intelligently
- **Voice input**: Use speech-to-text for hands-free invoice creation
- **Beautiful UI**: Modern React + Tailwind interface with dark mode
- **PDF-ready**: Professional HTML invoices ready for print/PDF conversion

## Setup

### 1. Install Python dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Node.js 20+ and frontend dependencies
```bash
# Install nvm if needed
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 20.19.0
nvm use 20.19.0

# Install and build frontend
cd web
npm install
npm run build
cd ..
```

### 3. Configure API keys
```bash
# Copy example and add your Anthropic API key
cp env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 4. Configure consultant settings
Edit `data/config.json` with your details:
- Name, email, address, phone
- Hourly rate, currency, tax rate
- Payment terms and instructions
- Logo path (optional): place logo at `assets/logo.png`

## Run

```bash
source .venv/bin/activate
export ANTHROPIC_API_KEY=your-key-here  # or source .env
uvicorn backend.app:app --reload
```

Open http://127.0.0.1:8000

## Usage

### AI-Assisted Invoice (freeform text)

1. Type or speak your work description:
```
For Acme Corp, September billing. Total 18.5 hours.
- Architecture review: complex system design
- API gateway setup: routing and auth
- Documentation cleanup
- Team onboarding session
```

2. Click "Generate" → Claude allocates hours across subjects
3. Review the breakdown table
4. Click "Finalize & Generate Invoice"
5. Preview appears in right panel

### Calendar-Based Invoice

1. Enter client email in left sidebar
2. Choose date range or quick range (Current/Last Month)
3. Click "Fetch Calendar Data"
4. Review fetched meetings
5. Click "Preview Invoice"

## API Endpoints

- `POST /stt` - Speech-to-text (Vosk)
- `POST /ai-invoice/allocate` - Allocate hours via Claude
- `POST /ai-invoice/finalize` - Generate invoice HTML
- `GET /invoices/{filename}` - Serve generated invoices

## Project Structure

```
invoy/
├── backend/          # FastAPI backend
│   ├── app.py        # Main API
│   ├── ai.py         # Claude integration
│   ├── stt.py        # Speech-to-text
│   └── utils.py      # Invoice rendering
├── web/              # React + Vite + Tailwind frontend
├── templates/        # Jinja2 invoice templates
├── data/             # Config and sample data
├── output/           # Generated invoices
└── scripts/          # Utility scripts
```

## Credits

- Claude 3.5 Sonnet (Anthropic) for intelligent allocation
- Vosk for offline speech recognition
- FastAPI + React + Tailwind for modern UX