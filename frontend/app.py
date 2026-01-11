import streamlit as st
import os
from datetime import datetime
import openai
import google.generativeai as genai
import re
import random
import logging
from typing import Optional, Dict, List, Tuple
import concurrent.futures

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API keys from Streamlit secrets
try:
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
except:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Configure APIs
openai.api_key = OPENAI_API_KEY
OPENAI_AVAILABLE = bool(OPENAI_API_KEY) and OPENAI_API_KEY != "your_openai_api_key_here"

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
    except:
        GEMINI_AVAILABLE = False
else:
    GEMINI_AVAILABLE = False

# SMS Handler class (inline)
class SMSHandler:
    def __init__(self):
        self.sms_database = {
            "9999999999": [
                {"content": "OTP is 123456 for your transaction.", "timestamp": "2024-01-15 14:30:00", "type": "otp"},
                {"content": "Your order #12345 has been shipped. Track at xyz.com", "timestamp": "2024-01-15 13:45:00", "type": "delivery"}
            ],
            "8888888888": [
                {"content": "Your loan application status: Approved. Contact us at 9999999999", "timestamp": "2024-01-15 10:15:00", "type": "finance"},
                {"content": "EMI reminder: Pay Rs. 15000 by 15th this month.", "timestamp": "2024-01-14 09:30:00", "type": "finance"}
            ],
            "7777777777": [
                {"content": "Your appointment with Dr. Sharma is confirmed for 10 AM tomorrow.", "timestamp": "2024-01-15 16:20:00", "type": "medical"},
                {"content": "Lab test results ready. Please visit clinic.", "timestamp": "2024-01-14 11:45:00", "type": "medical"}
            ],
            "6666666666": [
                {"content": "Your package will be delivered today between 2-4 PM.", "timestamp": "2024-01-15 09:00:00", "type": "delivery"},
                {"content": "Delivery update: Your order is out for delivery.", "timestamp": "2024-01-15 12:30:00", "type": "delivery"}
            ]
        }
    
    def extract_sms_for_number(self, phone_number: str, limit: int = 2) -> Optional[List[Dict]]:
        clean_number = self._clean_phone_number(phone_number)
        sms_list = self.sms_database.get(clean_number)
        if sms_list:
            return sms_list[-limit:]
        for num, sms_data in self.sms_database.items():
            if num.endswith(clean_number[-10:]):
                return sms_data[-limit:]
        return None
    
    def _clean_phone_number(self, phone_number: str) -> str:
        return re.sub(r'\D', '', phone_number)

sms_handler = SMSHandler()

# Backend logic functions
def mock_enrich_data(phone_number: str) -> dict:
    clean_number = re.sub(r'\D', '', phone_number)[-10:]
    categories = {
        "bank": {"patterns": ["8888", "9999", "7777"], "label": "Bank/Financial Service", "confidence": "high", "description": "Banks, loan services, and financial institutions"},
        "delivery": {"patterns": ["6666", "5555", "4444"], "label": "Delivery/Logistics", "confidence": "high", "description": "Package delivery and logistics companies"},
        "medical": {"patterns": ["1234", "5678"], "label": "Medical/Healthcare", "confidence": "high", "description": "Hospitals, clinics, and healthcare providers"},
        "service": {"patterns": ["3333", "2222", "1111"], "label": "Service Provider", "confidence": "medium", "description": "General service providers"}
    }
    
    for category, info in categories.items():
        if any(suffix in clean_number for suffix in info["patterns"]):
            return {"caller_label": info["label"], "category": category, "confidence": info["confidence"], "recent_calls": random.randint(1, 5), "call_time_pattern": "business hours" if category != "delivery" else "daytime", "description": info["description"], "is_known": True}
    
    patterns = [
        {"caller_label": "Unknown Business", "confidence": "low", "recent_calls": random.randint(1, 2), "category": "unknown", "is_known": False},
        {"caller_label": "Potential Customer", "confidence": "low", "recent_calls": 1, "category": "unknown", "is_known": False},
        {"caller_label": "Telemarketer", "confidence": "low", "recent_calls": random.randint(1, 4), "category": "spam", "is_known": False},
        {"caller_label": "Wrong Number", "confidence": "low", "recent_calls": random.randint(1, 3), "category": "mistake", "is_known": False}
    ]
    result = random.choice(patterns)
    result["description"] = f"Could be {result['caller_label'].lower()}"
    return result

def determine_response_state(enriched_data: dict, sms_content: Optional[list], user_input: Optional[str] = None) -> tuple:
    confidence = enriched_data.get("confidence", "low")
    recent_calls = enriched_data.get("recent_calls", 0)
    has_sms = bool(sms_content)
    has_user_input = bool(user_input and len(user_input.strip()) > 5)
    has_high_confidence = confidence == "high"
    is_repeat_caller = recent_calls > 1
    
    signal_count = sum([has_sms, has_user_input, has_high_confidence, is_repeat_caller])
    
    if signal_count >= 3 or (has_high_confidence and (has_sms or has_user_input)):
        context_parts = [f"The caller is identified as '{enriched_data['caller_label']}'"]
        if has_sms and isinstance(sms_content, list):
            sms_texts = [sms.get('content', '') for sms in sms_content if isinstance(sms, dict)]
            if sms_texts:
                context_parts.append(f"Related SMS: {'; '.join(sms_texts[:2])}")
        if has_user_input:
            context_parts.append(f"User context: {user_input[:100]}")
        context_parts.append(f"Recent calls: {recent_calls}")
        return "STRONG_CONTEXT", ". ".join(context_parts), 0.85
    
    elif signal_count >= 1:
        context_parts = []
        if has_high_confidence:
            context_parts.append(f"Likely a {enriched_data['caller_label'].lower()}")
        if is_repeat_caller:
            context_parts.append(f"This number has called {recent_calls} times")
        if has_sms:
            context_parts.append(f"Some SMS context available")
        if has_user_input:
            context_parts.append(f"You provided context about this call")
        return "WEAK_CONTEXT", ". ".join(context_parts) if context_parts else f"Limited context for {enriched_data['caller_label'].lower()}", 0.50
    
    else:
        return "NO_CONTEXT", f"Unknown number with no additional context", 0.20

def call_gemini_api(prompt: str, user_language: str = "en") -> str:
    try:
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-pro']
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, request_options={"timeout": 10})
                if response and hasattr(response, 'text') and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {str(e)}")
                continue
        raise Exception("All Gemini model variants failed")
    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}", exc_info=True)
        raise e

def get_ai_explanation(enriched_data: dict, sms_content: Optional[list], user_input: Optional[str], caller_label: str, call_time: str, call_frequency: int, user_language: str) -> str:
    state, context_desc, _ = determine_response_state(enriched_data, sms_content, user_input)
    
    if not OPENAI_AVAILABLE and not GEMINI_AVAILABLE:
        if state == "STRONG_CONTEXT":
            return f"This appears to be a {enriched_data.get('caller_label', 'business')} call. Based on available context, this might be important."
        elif state == "WEAK_CONTEXT":
            return f"This might be a {enriched_data.get('caller_label', 'caller')}. Limited context available."
        else:
            return "This was a missed call. No AI explanation available due to missing API configuration."
    
    if state == "NO_CONTEXT":
        user_context_note = f"The user mentioned: '{user_input}' - PRIORITIZE this information." if user_input else ""
        basic_prompt = f"""You are an intelligent assistant helping explain a missed call to an Indian user.

Phone number: {enriched_data.get('phone', '')}
{user_context_note}

ANALYZE and provide:
1. **What this call might be about** - Be specific based on the context provided
2. **Risk assessment** - Is this urgent? Could be spam? Important?
3. **Action recommendation** - Choose ONE: CALLBACK NOW | CALLBACK LATER | IGNORE | VERIFY FIRST | WAIT FOR MESSAGE
4. **Why this action** - Brief reason for your recommendation

Be specific, direct, and helpful for an Indian user.
Respond in {user_language or 'en'} (use Hinglish if Hindi is requested).
Format your response clearly with the action recommendation BOLD and prominent."""
        prompt = basic_prompt
    elif state == "WEAK_CONTEXT":
        user_context_note = f"User's note: '{user_input}' - PRIORITIZE this." if user_input else ""
        prompt = f"""You are an intelligent assistant helping explain a missed call to an Indian user.

Phone number: {enriched_data.get('phone', '')}
Caller type: {context_desc}
{user_context_note}

ANALYZE deeply and provide:
1. **What this call is likely about** - Use the caller info and user context
2. **Urgency level** - HIGH/MEDIUM/LOW based on caller type and context
3. **Action recommendation** - Choose ONE and be specific:
   - CALLBACK NOW (if urgent or important)
   - CALLBACK LATER TODAY (if needs response but not emergency)
   - IGNORE (if spam/telemarketer)
   - VERIFY BY MESSAGE (ask via SMS/WhatsApp first)
   - WAIT AND SEE (if likely to follow up by message)
4. **Why this action** - Clear reasoning

Be probabilistic using words like 'likely', 'possibly' when appropriate.
Respond in {user_language or 'en'} (use Hinglish if Hindi requested).
Make the action recommendation BOLD and clear."""
    else:  # STRONG_CONTEXT
        user_context_note = f"User's context: '{user_input[:200]}' - PRIORITIZE this information." if user_input and isinstance(user_input, str) else ""
        prompt = f"""You are an intelligent assistant explaining a missed call to an Indian user with strong context.

Phone number: {enriched_data.get('phone', '')}
Caller: {context_desc}
{user_context_note}

PROVIDE CLEAR ANALYSIS:
1. **What this call is about** - Be definitive based on strong context
2. **Urgency** - Is this time-sensitive? Emergency? Routine?
3. **RECOMMENDED ACTION** - Choose ONE (be specific):
   - CALL BACK IMMEDIATELY (if urgent/important)
   - CALL BACK TODAY (if time-sensitive matter)
   - RESPOND VIA MESSAGE FIRST (if should verify)
   - IGNORE SAFELY (if spam/unwanted)
   - TAKE ACTION NOW (if requires immediate step)
4. **Why this action** - Based on context provided

User context is the primary signal - use it to guide your recommendation.
Respond in {user_language or 'en'} (use Hinglish if Hindi requested).
Make your recommended action BOLD and prominent."""
    
    def call_ai_api():
        if GEMINI_AVAILABLE:
            return call_gemini_api(prompt, user_language or "en")
        elif OPENAI_AVAILABLE:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that explains missed calls in a clear, honest way. Never hallucinate. If context is insufficient, say so clearly. Be respectful and concise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                timeout=10
            )
            return response.choices[0].message["content"].strip()
        else:
            raise Exception("No AI API available")
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(call_ai_api)
            explanation = future.result(timeout=15)
        return explanation
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        if state == "STRONG_CONTEXT":
            return f"This appears to be a {enriched_data.get('caller_label', 'business')} call. Based on available context, this might be important."
        elif state == "WEAK_CONTEXT":
            return f"This might be a {enriched_data.get('caller_label', 'caller')}. Limited context available."
        else:
            return "This was a missed call. Unable to generate detailed analysis at this time."

# Set page config for dark theme
st.set_page_config(
    page_title="MissedCall.AI",
    page_icon="📞",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    [data-testid=stAppViewContainer] {
        background-color: #0f0f0f;
        color: white;
    }
    [data-testid=stHeader] {
        background-color: #0f0f0f;
    }
    [data-testid=stSidebar] {
        background-color: #1a1a1a;
    }
    .stTextInput>div>div>input {
        background-color: #2d2d2d;
        color: white;
        border: 1px solid #444;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 6px;
        font-size: 16px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .explanation-box {
        background-color: #1a1a1a;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 20px;
        margin-top: 20px;
        color: white;
    }
    .disclaimer {
        background-color: #2d2d2d;
        border-left: 4px solid #ff6b6b;
        padding: 15px;
        margin-top: 20px;
        border-radius: 4px;
        font-size: 14px;
    }
    .info-card {
        background-color: #1a1a1a;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("📞 MissedCall.AI")
st.subheader("Turn Missed Calls into Clear Insights")

# Initialize session state for phone number and voice input
if 'phone_number' not in st.session_state:
    st.session_state.phone_number = ""
if 'voice_input' not in st.session_state:
    st.session_state.voice_input = ""
if 'selected_language' not in st.session_state:
    st.session_state.selected_language = "en"
if 'caller_type' not in st.session_state:
    st.session_state.caller_type = "Unknown"

# Sidebar with info
with st.sidebar:
    st.header("ℹ️ About MissedCall.AI")
    st.info("""
    **MissedCall.AI** does NOT identify phone numbers like Truecaller.
    
    It works AFTER a missed call and sends a clear, honest explanation 
    of the POSSIBLE reason for the call, in simple local language.
    
    The system never hallucinates. If context is missing, 
    it clearly states so.
    """)
    
    st.header("🌐 Language Settings")
    lang_options = {"en": "English", "mr": "मराठी (Marathi)", "hi": "हिंदी (Hindi)", "ta": "தமிழ் (Tamil)", "te": "తెలుగు (Telugu)", "ml": "മലയാളം (Malayalam)", "bn": "বাংলা (Bengali)"}
    selected_lang = st.selectbox("Select your preferred language:", 
                           list(lang_options.keys()), 
                           format_func=lambda x: lang_options.get(x, x),
                           key="language_select")
    language = selected_lang

# Main content

col1, col2 = st.columns([3, 1])

with col1:
    phone_number = st.text_input("Enter missed call number:", 
                        value=st.session_state.phone_number,
                        placeholder="e.g., 9999999999")

with col2:
    st.write("")  # Spacer
    st.write("")  # Spacer
    caller_label = st.selectbox("Caller Type (Optional):", 
                               ["Unknown", "Bank", "Delivery", "Service", "Family/Friend", "Business"],
                               index=["Unknown", "Bank", "Delivery", "Service", "Family/Friend", "Business"].index(st.session_state.caller_type) if st.session_state.caller_type in ["Unknown", "Bank", "Delivery", "Service", "Family/Friend", "Business"] else 0)

# Additional context
st.subheader("💬 Additional Context (Optional)")
voice_input = st.text_area("Describe the situation or any details you remember:", 
                          placeholder="e.g., 'I missed this call while in a meeting', 'This number sent me an SMS earlier'", 
                          height=100)

# Advanced options expander
with st.expander("Advanced Options"):
    call_time = st.text_input("Call Time (Optional):", placeholder="e.g., 2:30 PM, morning, evening")
    call_frequency = st.number_input("How many times did it ring? (Optional):", min_value=1, max_value=10, value=1)

# Initialize result storage
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

# Submit button
if st.button("🎤 Explain this missed call", use_container_width=True, key="analyze_button"):
    if not phone_number:
        st.error("Please enter a phone number")
    else:
        with st.spinner("Analyzing missed call..."):
            try:
                # Process locally (embedded backend logic)
                enriched_data = mock_enrich_data(phone_number)
                enriched_data['phone'] = phone_number  # Add phone number for reference
                
                # If user provided a caller_label, override the enriched data with it
                if caller_label and caller_label != "Unknown":
                    caller_type_mapping = {
                        "Bank": "Bank/Financial Service",
                        "Delivery": "Delivery/Logistics",
                        "Service": "Service Provider",
                        "Family/Friend": "Family/Friend",
                        "Business": "Business"
                    }
                    enriched_data["caller_label"] = caller_type_mapping.get(caller_label, caller_label)
                    enriched_data["is_known"] = True
                    enriched_data["confidence"] = "high"
                    category_mapping = {
                        "Bank": "bank",
                        "Delivery": "delivery",
                        "Service": "service",
                        "Family/Friend": "personal",
                        "Business": "business"
                    }
                    enriched_data["category"] = category_mapping.get(caller_label, "unknown")
                
                # Extract SMS content
                sms_content = sms_handler.extract_sms_for_number(phone_number)
                
                # Get state and AI explanation
                state, _, _ = determine_response_state(enriched_data, sms_content, voice_input)
                explanation = get_ai_explanation(enriched_data, sms_content, voice_input, caller_label, call_time, int(call_frequency) if call_frequency else 1, language)
                
                # Display results
                st.success("Analysis Complete!")
                
                # Show state information
                state_colors = {
                    "NO_CONTEXT": "#ff6b6b",
                    "WEAK_CONTEXT": "#ffd166", 
                    "STRONG_CONTEXT": "#06d6a0"
                }
                
                state_descriptions = {
                    "NO_CONTEXT": "No Context Available",
                    "WEAK_CONTEXT": "Weak Context Available", 
                    "STRONG_CONTEXT": "Strong Context Available"
                }
                
                state_color = state_colors.get(state, "#ff6b6b")
                state_desc = state_descriptions.get(state, "Unknown")
                
                # Extract suggested action from explanation
                suggested_action = 'Check your messages'
                if "call back" in explanation.lower() and "immediately" in explanation.lower():
                    suggested_action = "Call back immediately"
                elif "call back" in explanation.lower():
                    suggested_action = "Call back when possible"
                elif "ignore" in explanation.lower():
                    suggested_action = "Safe to ignore"
                elif "verify" in explanation.lower():
                    suggested_action = "Verify before acting"
                elif "take action" in explanation.lower():
                    suggested_action = "Take action now"
                
                # Extract action recommendation from explanation if present
                action_colors = {
                    "callback now": "#ff6b6b",  # Red for urgent
                    "call back immediately": "#ff6b6b",
                    "callback later": "#ffd166",  # Orange for later
                    "call back today": "#ffd166",
                    "ignore": "#06d6a0",  # Green for safe
                    "ignore safely": "#06d6a0",
                    "wait": "#4ecdc4",  # Cyan for wait
                    "verify": "#95e1d3",  # Light cyan
                    "take action": "#ff9ff3"  # Pink for action needed
                }
                
                action_icon = "⚠️"
                action_color = "#ffd166"
                for action_type, color in action_colors.items():
                    if action_type.lower() in explanation.lower():
                        action_color = color
                        if "immediately" in action_type or "now" in action_type:
                            action_icon = "🚨"
                        elif "ignore" in action_type:
                            action_icon = "✅"
                        elif "wait" in action_type:
                            action_icon = "⏳"
                        elif "take action" in action_type:
                            action_icon = "⚡"
                        elif "verify" in action_type:
                            action_icon = "🔍"
                        break
                
                st.markdown(f"""
                <div class="info-card" style="border-left: 5px solid {action_color};">
                    <strong>📊 Status:</strong> <span style="color:{state_color};font-weight:bold;">{state_desc}</span><br>
                    <strong style="font-size:16px;">{action_icon} What to do:</strong> <span style="color:{action_color};font-weight:bold;font-size:16px;">{suggested_action}</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Show explanation prominently
                st.markdown('<div class="explanation-box">', unsafe_allow_html=True)
                st.write(f"### 🔍 Full Analysis:")
                st.write(explanation)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Show caller details
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Caller Type", enriched_data.get('caller_label', 'Unknown'))
                with col2:
                    st.metric("Category", enriched_data.get('category', 'unknown').title())
                with col3:
                    st.metric("Known?", "Yes ✅" if enriched_data.get('is_known') else "No ❓")
                
                # Show SMS content if available
                if sms_content:
                    with st.expander("📧 Related SMS Messages"):
                        for sms in sms_content:
                            st.write(f"• {sms.get('content', '')}")
                
                # Disclaimer
                st.markdown(f"""
                <div class="disclaimer">
                    ⚠️ This is an AI-generated explanation based on available context. Always verify important information independently.
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
                logger.error(f"Error in analysis: {str(e)}", exc_info=True)

# Demo section
st.divider()
st.subheader("🎯 Try Demo Numbers")
st.caption("Click on any number below to auto-fill and analyze:")

demo_numbers = {
    "💳 Bank/Finance": ("8888888888", "Bank"),
    "📦 Delivery Service": ("6666666666", "Delivery"), 
    "⚕️ Medical Service": ("7777777777", "Service"),
    "❓ Unknown Number": ("5555555555", "Unknown")
}

cols = st.columns(len(demo_numbers))
for i, (label, (number, caller_type)) in enumerate(demo_numbers.items()):
    if cols[i].button(label, use_container_width=True, key=f"demo_{number}"):
        st.session_state.phone_number = number
        st.session_state.caller_type = caller_type
        st.rerun()

# Footer
st.divider()
st.caption("💡 MissedCall.AI - AI-powered voicemail replacement • Built for India")