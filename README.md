# MissedCall.AI — MVP

## Purpose
MissedCall.AI is an AI-powered voicemail replacement for missed calls in India. Instead of identifying phone numbers like Truecaller, it works AFTER a missed call and sends a clear, honest explanation of the POSSIBLE reason for the call, in simple local language.

## Features
- Analyzes missed calls with contextual information
- Supports multiple Indian languages (English, Marathi, Hindi, Tamil, Telugu, Malayalam, Bengali)
- Handles SMS context automatically
- Provides 3-tier response system (No Context, Weak Context, Strong Context)
- Dark mode interface
- **Auto-selected caller types for demo mode**
- PostgreSQL & scikit-learn ready for ML features

## Tech Stack
- Backend: FastAPI (Python)
- Frontend: Streamlit
- AI: OpenAI API & Google Gemini
- Database: PostgreSQL (pgml)
- ML: scikit-learn
- Theme: DARK MODE

## Setup Instructions

### Local Development

#### 1. Clone and Setup Environment
```bash
git clone https://github.com/Vaibhav2422/MissedCall.AI.git
cd MissedCall.AI
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env file
```

#### 2. Run Backend Server
```bash
uvicorn backend.main:app --reload --port 8000
```

#### 3. Run Frontend
In a new terminal:
```bash
streamlit run frontend/app.py
```

The app will be available at `http://localhost:8501`

### Streamlit Cloud Deployment

#### 1. Push to GitHub
```bash
git push origin main
```

#### 2. Deploy on Streamlit Cloud
- Go to [share.streamlit.io](https://share.streamlit.io)
- Click "New app" → Connect GitHub repo
- Select `main` branch and `frontend/app.py` as main file
- Click Deploy

#### 3. Configure Secrets
In Streamlit Cloud dashboard, go to App settings → Secrets and add:
```toml
OPENAI_API_KEY = "your_key_here"
GEMINI_API_KEY = "your_key_here"
```

#### System Dependencies
The `packages.txt` file automatically installs:
- `libpq-dev` - PostgreSQL development libraries
- `build-essential` - Compiler for building packages

## API Endpoints

### POST `/explain`
Explain a missed call with the following request body:
```json
{
  "phone_number": "string",
  "caller_label": "string (optional)",
  "call_time": "string (optional)",
  "call_frequency": "int (optional)",
  "voice_input": "string (optional)",
  "user_language": "string (default: 'en')"
}
```

Response includes:
- `explanation`: AI-generated explanation
- `state`: NO_CONTEXT, WEAK_CONTEXT, or STRONG_CONTEXT
- `confidence`: Confidence level
- `metadata`: Enriched data
- `sms_content`: Related SMS messages (if any)
- `suggested_action`: Recommended next step

### GET `/health`
Health check endpoint

## Architecture

### Backend (`backend/main.py`)
- FastAPI server
- Mock data enrichment with automatic caller type detection
- SMS context extraction
- OpenAI & Gemini integration
- 3-tier response logic
- Multi-language support

### Frontend (`frontend/app.py`)
- Streamlit dark-themed UI
- Phone number input
- Auto-selected caller types for demo buttons
- Language preferences (7 languages)
- Real-time analysis
- Visual status indicators

## Response States

### STATE A: NO CONTEXT
Returned when number is unknown and no metadata exists:
> "This was a missed call from an unknown number. There is not enough information to determine the reason."

### STATE B: WEAK CONTEXT
Returned when partial signals exist:
> Uses words like "likely", "possibly", "may be"

### STATE C: STRONG CONTEXT
Returned when clear metadata exists:
> Provides clear explanation with suggested next action

## Demo Features

Click any demo button to auto-fill:
- **💳 Bank/Finance** → Automatically selects "Bank" caller type
- **📦 Delivery Service** → Automatically selects "Delivery" caller type
- **⚕️ Medical Service** → Automatically selects "Service" caller type
- **❓ Unknown Number** → Leaves caller type as "Unknown"

## Database Support

For production use with PostgreSQL and pgml:

```sql
CREATE TABLE missed_calls (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20),
    caller_type VARCHAR(50),
    explanation TEXT,
    context_state VARCHAR(20),
    language VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## License
MIT

## Privacy & Ethics
- Never claims unauthorized access to personal messages
- Always transparent about limitations
- Never hallucinates information
- Respects user privacy

