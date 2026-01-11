# MissedCall.AI — MVP

## Purpose
MissedCall.AI is an AI-powered voicemail replacement for missed calls in India. Instead of identifying phone numbers like Truecaller, it works AFTER a missed call and sends a clear, honest explanation of the POSSIBLE reason for the call, in simple local language.

## Features
- Analyzes missed calls with contextual information
- Supports multiple Indian languages (English, Marathi, Hindi, Tamil, Telugu, Malayalam, Bengali)
- Handles SMS context automatically
- Provides 3-tier response system (No Context, Weak Context, Strong Context)
- Dark mode interface

## Tech Stack
- Backend: FastAPI (Python)
- Frontend: Streamlit
- AI: OpenAI API
- Theme: STRICT DARK MODE ONLY

## Setup Instructions

### 1. Clone and Setup Environment
```bash
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env file

# Note: On some systems, you might need to install PyAudio separately:
# pip install pipwin
# pipwin install pyaudio
```

### 2. Run Backend Server
```bash
uvicorn backend.main:app --reload --port 8000
```

### 3. Run Frontend
In a new terminal:
```bash
streamlit run frontend/app.py
```

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

### GET `/health`
Health check endpoint

### POST `/speech_to_text`
Convert speech audio to text. Accepts audio files (wav, mp3, m4a, flac) and returns transcribed text.

## Architecture

### Backend (`backend/main.py`)
- FastAPI server
- Mock data enrichment
- SMS context extraction
- OpenAI integration
- 3-tier response logic

### Frontend (`frontend/app.py`)
- Streamlit dark-themed UI
- Phone number input
- Context selection
- Language preferences
- Real-time analysis

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

## Privacy & Ethics
- Never claims unauthorized access to personal messages
- Always transparent about limitations
- Never hallucinates information
- Respects user privacy

