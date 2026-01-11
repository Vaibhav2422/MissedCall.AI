import streamlit as st
import requests
import os
from datetime import datetime
import sys
import re

# Try to import backend functions directly
try:
    from backend.main import mock_enrich_data, determine_response_state, call_gemini_api
    from backend.sms_handler import SMSHandler
    BACKEND_AVAILABLE = True
except:
    BACKEND_AVAILABLE = False
    # Fallback functions
    def mock_enrich_data(phone_number):
        return {
            "caller_label": "Unknown",
            "category": "unknown",
            "confidence": "low",
            "is_known": False
        }
    
    def determine_response_state(enriched_data, sms_content, user_input):
        return "NO_CONTEXT", "No context available", 0.2
    
    class SMSHandler:
        def extract_sms_for_number(self, phone_number):
            return None

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
        # Prepare request payload
        payload = {
            "phone_number": phone_number,
            "caller_label": caller_label if caller_label != "Unknown" else None,
            "call_time": call_time or None,
            "call_frequency": int(call_frequency) if call_frequency else None,
            "voice_input": voice_input or None,
            "user_language": language
        }
        
        with st.spinner("Analyzing missed call..."):
            try:
                # Try local backend first, then fall back to HTTP
                if BACKEND_AVAILABLE:
                    # Use backend directly
                    sms_handler = SMSHandler()
                    enriched_data = mock_enrich_data(phone_number)
                    
                    # Override with user selection
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
                    
                    sms_content = sms_handler.extract_sms_for_number(phone_number)
                    state, context_desc, confidence_score = determine_response_state(enriched_data, sms_content, voice_input)
                    
                    # Generate explanation using Gemini
                    import openai
                    import google.generativeai as genai
                    from dotenv import load_dotenv
                    
                    load_dotenv()
                    gemini_api_key = os.getenv("GEMINI_API_KEY")
                    if gemini_api_key:
                        genai.configure(api_key=gemini_api_key)
                        try:
                            prompt = f"""You are an intelligent assistant helping explain a missed call to an Indian user.

Phone number: {phone_number}
Caller: {enriched_data.get('caller_label', 'Unknown')}
{"User's note: " + voice_input if voice_input else ""}

Provide:
1. **What this call is likely about**
2. **Risk assessment** - Is this urgent? Could be spam?
3. **Action recommendation** - CALLBACK NOW, CALLBACK LATER, IGNORE, VERIFY FIRST, or WAIT
4. **Why this action**

Be specific and helpful for an Indian user.
Respond in {language}.
Make your recommendation BOLD."""
                            
                            model = genai.GenerativeModel('gemini-2.0-flash')
                            response = model.generate_content(prompt)
                            explanation = response.text if response else "Unable to generate explanation"
                        except:
                            explanation = f"This appears to be a {enriched_data.get('caller_label', 'missed')} call. Please check manually."
                    else:
                        explanation = f"This appears to be a {enriched_data.get('caller_label', 'missed')} call."
                    
                    result = {
                        "explanation": explanation,
                        "state": state,
                        "caller_info": {
                            "label": enriched_data.get('caller_label'),
                            "category": enriched_data.get('category', 'unknown'),
                            "is_known": enriched_data.get('is_known', False)
                        },
                        "sms_content": [sms['content'] for sms in sms_content] if sms_content else None,
                        "suggested_action": "Check the analysis above"
                    }
                else:
                    # Try HTTP backend
                    response = requests.post("http://localhost:8000/explain", json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        result = response.json()
                    else:
                        st.error(f"Error: {response.status_code} - {response.text}")
                        st.stop()
                
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
                    
                    state_color = state_colors.get(result.get("state", "NO_CONTEXT"), "#ff6b6b")
                    state_desc = state_descriptions.get(result.get("state", "NO_CONTEXT"), "Unknown")
                    suggested_action = result.get('suggested_action', 'Check your messages')
                    
                    # Extract action recommendation from explanation if present
                    explanation_text = result["explanation"]
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
                        if action_type.lower() in explanation_text.lower():
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
                    st.write(result["explanation"])
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Show caller details
                    caller_info = result.get("caller_info", {})
                    if caller_info:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Caller Type", caller_info.get('label', 'Unknown'))
                        with col2:
                            st.metric("Category", caller_info.get('category', 'unknown').title())
                        with col3:
                            st.metric("Known?", "Yes ✅" if caller_info.get('is_known') else "No ❓")
                    
                    # Show SMS content if available
                    sms_content = result.get("sms_content")
                    if sms_content:
                        with st.expander("📧 Related SMS Messages"):
                            st.write("\n".join(sms_content))
                    
                    # Disclaimer
                    st.markdown(f"""
                    <div class="disclaimer">
                        ⚠️ {result.get('disclaimer', 'This is an AI-generated explanation based on available context.')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to backend server. Please make sure the FastAPI server is running on http://localhost:8000")
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")

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