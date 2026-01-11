from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from typing import Optional, Dict, Any
import openai
import google.generativeai as genai
import os
from dotenv import load_dotenv
import random
import re
from datetime import datetime
import base64
from io import BytesIO
from pydub import AudioSegment
import tempfile
import speech_recognition as sr
from typing import List
import concurrent.futures
from functools import lru_cache
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SMSHandler:
    """Handles SMS content extraction and analysis for missed calls"""
    
    def __init__(self):
        # Mock SMS database for MVP
        self.sms_database = {
            "9999999999": [
                {
                    "content": "OTP is 123456 for your transaction.",
                    "timestamp": "2024-01-15 14:30:00",
                    "type": "otp"
                },
                {
                    "content": "Your order #12345 has been shipped. Track at xyz.com",
                    "timestamp": "2024-01-15 13:45:00", 
                    "type": "delivery"
                }
            ],
            "8888888888": [
                {
                    "content": "Your loan application status: Approved. Contact us at 9999999999",
                    "timestamp": "2024-01-15 10:15:00",
                    "type": "finance"
                },
                {
                    "content": "EMI reminder: Pay Rs. 15000 by 15th this month.",
                    "timestamp": "2024-01-14 09:30:00",
                    "type": "finance"
                }
            ],
            "7777777777": [
                {
                    "content": "Your appointment with Dr. Sharma is confirmed for 10 AM tomorrow.",
                    "timestamp": "2024-01-15 16:20:00",
                    "type": "medical"
                },
                {
                    "content": "Lab test results ready. Please visit clinic.",
                    "timestamp": "2024-01-14 11:45:00",
                    "type": "medical"
                }
            ],
            "6666666666": [
                {
                    "content": "Your package will be delivered today between 2-4 PM.",
                    "timestamp": "2024-01-15 09:00:00",
                    "type": "delivery"
                },
                {
                    "content": "Delivery update: Your order is out for delivery.",
                    "timestamp": "2024-01-15 12:30:00",
                    "type": "delivery"
                }
            ]
        }
    
    def extract_sms_for_number(self, phone_number: str, limit: int = 2) -> Optional[List[Dict]]:
        """
        Extract SMS messages for a given phone number
        
        Args:
            phone_number: The phone number to search for
            limit: Maximum number of recent SMS to return
            
        Returns:
            List of SMS dictionaries or None if no SMS found
        """
        clean_number = self._clean_phone_number(phone_number)
        
        # Look for exact match first
        sms_list = self.sms_database.get(clean_number)
        if sms_list:
            # Return most recent SMS up to limit
            return sms_list[-limit:]
        
        # If no exact match, try to find by partial match (last 10 digits)
        for num, sms_data in self.sms_database.items():
            if num.endswith(clean_number[-10:]):
                return sms_data[-limit:]
        
        return None
    
    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean phone number by removing non-digit characters"""
        return re.sub(r'\D', '', phone_number)
    
    def categorize_sms_type(self, sms_content: str) -> str:
        """
        Categorize SMS type based on content
        
        Args:
            sms_content: The SMS message content
            
        Returns:
            Category of the SMS
        """
        sms_lower = sms_content.lower()
        
        finance_keywords = ['bank', 'loan', 'emi', 'account', 'debit', 'credit', 'payment', 'balance', 'transaction', 'otp']
        delivery_keywords = ['order', 'package', 'shipment', 'delivery', 'track', 'dispatch', 'shipping']
        medical_keywords = ['appointment', 'doctor', 'clinic', 'lab', 'test', 'medical', 'hospital']
        utility_keywords = ['bill', 'electricity', 'water', 'gas', 'recharge', 'mobile']
        
        if any(keyword in sms_lower for keyword in finance_keywords):
            return 'finance'
        elif any(keyword in sms_lower for keyword in delivery_keywords):
            return 'delivery'
        elif any(keyword in sms_lower for keyword in medical_keywords):
            return 'medical'
        elif any(keyword in sms_lower for keyword in utility_keywords):
            return 'utility'
        else:
            return 'general'
    
    def extract_relevant_info(self, sms_content: str) -> Dict:
        """
        Extract relevant information from SMS content
        
        Args:
            sms_content: The SMS message content
            
        Returns:
            Dictionary with extracted information
        """
        info = {
            'amount': self._extract_amount(sms_content),
            'order_id': self._extract_order_id(sms_content),
            'tracking_info': self._extract_tracking_info(sms_content),
            'time_info': self._extract_time_info(sms_content),
            'company': self._extract_company(sms_content)
        }
        
        return {k: v for k, v in info.items() if v is not None}
    
    def _extract_amount(self, text: str) -> Optional[str]:
        """Extract monetary amounts from text"""
        amount_patterns = [
            r'Rs\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'INR\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'amount\s*[^\d]*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_order_id(self, text: str) -> Optional[str]:
        """Extract order IDs from text"""
        patterns = [
            r'order\s*#?\s*([A-Z0-9]+)',
            r'#[A-Z0-9]{6,}',
            r'order\s+id[:\s]+([A-Z0-9-]+)',
            r'ord(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_tracking_info(self, text: str) -> Optional[str]:
        """Extract tracking numbers from text"""
        patterns = [
            r'track(?:ing)?\s*[:\s]+([A-Z0-9]+)',
            r'tracking\s+id[:\s]+([A-Z0-9]+)',
            r'[A-Z]{2}[0-9]{9}[A-Z]{2}'  # Standard tracking format
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_time_info(self, text: str) -> Optional[str]:
        """Extract time-related information"""
        patterns = [
            r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)',
            r'(today|tomorrow|morning|afternoon|evening|night)',
            r'on\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
        ]
        
        times = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            times.extend(matches)
        
        return ', '.join(times) if times else None
    
    def _extract_company(self, text: str) -> Optional[str]:
        """Extract company names from text"""
        # Common company indicators in Indian context
        patterns = [
            r'from\s+([A-Z][A-Za-z\s&]+)(?:\s+Pvt\.?|Ltd\.?|LLC|Inc\.?)?',
            r'by\s+([A-Z][A-Za-z\s&]+)(?:\s+Pvt\.?|Ltd\.?|LLC|Inc\.?)?',
            r'([A-Z][A-Za-z\s&]+)\s+(?:customer|service|support)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Filter out common words that aren't companies
                if len(company) > 2 and not any(word in company.lower() for word in ['the', 'and', 'or']):
                    return company
        return None

# Use the existing SMS handler instance from sms_handler module
from .sms_handler import SMSHandler

# Create an instance of the SMS handler
sms_handler = SMSHandler()

# Load environment variables
try:
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
except:
    # If .env file has issues, try to get API key from environment
    openai.api_key = os.getenv("OPENAI_API_KEY", "")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# Configure Gemini API
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    GEMINI_AVAILABLE = True
else:
    GEMINI_AVAILABLE = False
    
# Global flag to track if OpenAI API is available
OPENAI_AVAILABLE = bool(openai.api_key) and openai.api_key != "your_openai_api_key_here"

if not OPENAI_AVAILABLE and not GEMINI_AVAILABLE:
    print("WARNING: No valid AI API key found. The app will run with fallback responses only.")
    print("Please set your OpenAI or Gemini API key in the .env file.")
elif GEMINI_AVAILABLE:
    print("✅ Gemini API configured and ready!")
elif OPENAI_AVAILABLE:
    print("✅ OpenAI API configured and ready!")

app = FastAPI()

class MissedCallRequest(BaseModel):
    phone_number: str
    caller_label: Optional[str] = None
    call_time: Optional[str] = None
    call_frequency: Optional[int] = None
    voice_input: Optional[str] = None
    user_language: Optional[str] = "en"  # en, hi, ta, te, etc.

def mock_enrich_data(phone_number: str) -> dict:
    """Enhanced data enrichment for the phone number with better confidence scoring"""
    # Extract digits from phone number for consistent matching
    clean_number = re.sub(r'\D', '', phone_number)[-10:]  # Get last 10 digits
    
    # Define categories with patterns
    categories = {
        "bank": {
            "patterns": ["8888", "9999", "7777"],
            "label": "Bank/Financial Service",
            "confidence": "high",
            "description": "Banks, loan services, and financial institutions"
        },
        "delivery": {
            "patterns": ["6666", "5555", "4444"],
            "label": "Delivery/Logistics",
            "confidence": "high",
            "description": "Package delivery and logistics companies"
        },
        "medical": {
            "patterns": ["1234", "5678"],
            "label": "Medical/Healthcare",
            "confidence": "high",
            "description": "Hospitals, clinics, and healthcare providers"
        },
        "service": {
            "patterns": ["3333", "2222", "1111"],
            "label": "Service Provider",
            "confidence": "medium",
            "description": "General service providers"
        }
    }
    
    # Check which category matches
    for category, info in categories.items():
        if any(suffix in clean_number for suffix in info["patterns"]):
            return {
                "caller_label": info["label"],
                "category": category,
                "confidence": info["confidence"],
                "recent_calls": random.randint(1, 5),
                "call_time_pattern": "business hours" if category != "delivery" else "daytime",
                "description": info["description"],
                "is_known": True
            }
    
    # Unknown number - assign probabilistically
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
    """
    Determine the response state based on multiple factors
    Returns (state, context_description, confidence_score)
    """
    confidence = enriched_data.get("confidence", "low")
    recent_calls = enriched_data.get("recent_calls", 0)
    is_known = enriched_data.get("is_known", False)
    
    # Calculate context signals
    has_sms = bool(sms_content)
    has_user_input = bool(user_input and len(user_input.strip()) > 5)
    has_high_confidence = confidence == "high"
    is_repeat_caller = recent_calls > 1
    
    # STATE C: STRONG_CONTEXT (3+ signals)
    signal_count = sum([has_sms, has_user_input, has_high_confidence, is_repeat_caller])
    
    if signal_count >= 3 or (has_high_confidence and (has_sms or has_user_input)):
        context_parts = [f"The caller is identified as '{enriched_data['caller_label']}'"]
        if has_sms:
            sms_texts = [sms['content'] for sms in sms_content]
            context_parts.append(f"Related SMS: {'; '.join(sms_texts[:2])}")
        if has_user_input:
            context_parts.append(f"User context: {user_input[:100]}")
        context_parts.append(f"Recent calls: {recent_calls}")
        
        return "STRONG_CONTEXT", ". ".join(context_parts), 0.85
    
    # STATE B: WEAK_CONTEXT (1-2 signals)
    elif signal_count >= 1:
        context_parts = []
        if has_high_confidence:
            context_parts.append(f"Likely a {enriched_data['caller_label'].lower()}")
        if is_repeat_caller:
            context_parts.append(f"This number has called {recent_calls} times")
        if has_sms:
            sms_texts = [sms['content'] for sms in sms_content]
            context_parts.append(f"Some SMS context available")
        if has_user_input:
            context_parts.append(f"You provided context about this call")
        
        return "WEAK_CONTEXT", ". ".join(context_parts) if context_parts else f"Limited context for {enriched_data['caller_label'].lower()}", 0.50
    
    # STATE A: NO_CONTEXT
    else:
        return "NO_CONTEXT", f"Unknown number with no additional context", 0.20

def call_gemini_api(prompt: str, user_language: str = "en") -> str:
    """Call Gemini API for AI explanation with improved error handling"""
    try:
        logger.info(f"Calling Gemini API with prompt length: {len(prompt)}")
        
        # Try multiple model versions - fallback if one doesn't work
        # Using latest available models with this API key
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-pro-latest']
        
        for model_name in models_to_try:
            try:
                logger.info(f"Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                
                # Generate response with simple call
                response = model.generate_content(prompt)
                
                if response and hasattr(response, 'text') and response.text:
                    logger.info(f"Gemini API response received with model {model_name}: {len(response.text)} chars")
                    return response.text.strip()
                    
            except Exception as model_err:
                logger.warning(f"Model {model_name} failed: {str(model_err)}")
                continue
        
        # If all models fail
        logger.error("All Gemini models failed")
        raise Exception("All Gemini model variants failed")
            
    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}", exc_info=True)
        raise e

@app.post("/explain")
async def explain_missed_call(req: MissedCallRequest):
    # Enrich the data with mock metadata
    enriched_data = mock_enrich_data(req.phone_number)
    
    # If user provided a caller_label, override the enriched data with it
    if req.caller_label and req.caller_label != "Unknown":
        # Map user-selected label to enriched_data
        caller_type_mapping = {
            "Bank": "Bank/Financial Service",
            "Delivery": "Delivery/Logistics",
            "Service": "Service Provider",
            "Family/Friend": "Family/Friend",
            "Business": "Business"
        }
        enriched_data["caller_label"] = caller_type_mapping.get(req.caller_label, req.caller_label)
        enriched_data["is_known"] = True
        enriched_data["confidence"] = "high"
        # Map to category
        category_mapping = {
            "Bank": "bank",
            "Delivery": "delivery",
            "Service": "service",
            "Family/Friend": "personal",
            "Business": "business"
        }
        enriched_data["category"] = category_mapping.get(req.caller_label, "unknown")
    
    # Check for related SMS content using the SMS handler
    sms_content = sms_handler.extract_sms_for_number(req.phone_number)
    
    # Determine response state with user input context
    state, context_desc, confidence_score = determine_response_state(enriched_data, sms_content, req.voice_input)
    
    # Check if AI API is available (OpenAI or Gemini)
    if not OPENAI_AVAILABLE and not GEMINI_AVAILABLE:
        # Return fallback response without attempting API call
        fallback_explanation = "This was a missed call. No AI explanation available due to missing API configuration."
        if state == "STRONG_CONTEXT":
            fallback_explanation = f"This appears to be a {enriched_data.get('caller_label', 'business')} call. Based on available context, this might be important."
        elif state == "WEAK_CONTEXT":
            fallback_explanation = f"This might be a {enriched_data.get('caller_label', 'caller')}. Limited context available."
        
        # Prepare SMS content for response
        sms_response = None
        if sms_content:
            sms_response = [sms['content'] for sms in sms_content]
        
        return {
            "explanation": fallback_explanation,
            "state": state,
            "caller_info": {
                "label": enriched_data.get('caller_label'),
                "category": enriched_data.get('category', 'unknown'),
                "is_known": enriched_data.get('is_known', False)
            },
            "disclaimer": "AI explanation unavailable due to missing API configuration. This is a fallback response based on available context.",
            "metadata": enriched_data,
            "sms_content": sms_response,
            "suggested_action": "Unknown - Please check manually"
        }
    
    # Prepare the prompt based on state
    if state == "NO_CONTEXT":
        # Build prompt with user context as primary signal
        user_context_note = ""
        if req.voice_input:
            user_context_note = f"The user mentioned: '{req.voice_input}' - PRIORITIZE this information in your answer."
        
        basic_prompt = f"""You are an intelligent assistant helping explain a missed call to an Indian user.

Phone number: {req.phone_number}
{user_context_note}

ANALYZE and provide:
1. **What this call might be about** - Be specific based on the context provided
2. **Risk assessment** - Is this urgent? Could be spam? Important?
3. **Action recommendation** - Choose ONE of these:
   - CALLBACK NOW (if urgent/important)
   - CALLBACK LATER (if not urgent but should follow up)
   - IGNORE (if likely spam/wrong number)
   - VERIFY FIRST (call back from different method/check with friends)
   - WAIT FOR MESSAGE (if likely to send message about purpose)
4. **Why this action** - Brief reason for your recommendation

Be specific, direct, and helpful for an Indian user.
Respond in {req.user_language} (use Hinglish if Hindi is requested).
Format your response clearly with the action recommendation BOLD and prominent."""
        
        import concurrent.futures
        
        def call_ai_api():
            """Try Gemini first (free), then OpenAI for NO_CONTEXT"""
            if GEMINI_AVAILABLE:
                print(f"DEBUG: Making Gemini API call for NO_CONTEXT")  # Debug log
                print(f"DEBUG: Prompt length: {len(basic_prompt)}")  # Debug log
                return call_gemini_api(basic_prompt, req.user_language)
            elif OPENAI_AVAILABLE:
                print(f"DEBUG: Making OpenAI API call with key: {openai.api_key[:10]}...")  # Debug log
                print(f"DEBUG: Prompt length: {len(basic_prompt)}")  # Debug log
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that explains missed calls in a clear, honest way. Never hallucinate. If context is insufficient, say so clearly. Be respectful and concise."},
                        {"role": "user", "content": basic_prompt}
                    ],
                    max_tokens=100,
                    timeout=10
                )
                return response.choices[0].message["content"].strip()
            else:
                raise Exception("No AI API available")
        
        try:
            # Execute with timeout using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(call_ai_api)
                explanation = future.result(timeout=15)  # 15 second timeout

            # Prepare SMS content for response
            sms_response = None
            if sms_content:
                sms_response = [sms['content'] for sms in sms_content]
            
            return {
                "explanation": explanation,
                "state": state,
                "confidence": "neutral",
                "disclaimer": "This is an AI-generated explanation based on available context.",
                "metadata": enriched_data,
                "sms_content": sms_response
            }
        except Exception as e:
            import traceback
            logger.error(f"API Error in NO_CONTEXT: {str(e)}")
            sms_response = None
            if sms_content:
                sms_response = [sms['content'] for sms in sms_content]
            return {
                "explanation": "This was a missed call from an unknown number. There is not enough information to determine the reason.",
                "state": state,
                "caller_info": {
                    "label": enriched_data.get('caller_label'),
                    "category": enriched_data.get('category', 'unknown'),
                    "is_known": enriched_data.get('is_known', False)
                },
                "suggested_action": "Try calling back to identify the caller",
                "disclaimer": "Limited information available for this call.",
                "metadata": enriched_data,
                "sms_content": sms_response
            }

    elif state == "WEAK_CONTEXT":
        # Create a prompt for weak context - user input is priority
        user_context_note = ""
        if req.voice_input:
            user_context_note = f"User's note: '{req.voice_input}' - PRIORITIZE this."
        
        prompt = f"""You are an intelligent assistant helping explain a missed call to an Indian user.

Phone number: {req.phone_number}
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
Respond in {req.user_language} (use Hinglish if Hindi requested).
Make the action recommendation BOLD and clear."""

    else:  # STRONG_CONTEXT
        user_context_note = ""
        if req.voice_input and isinstance(req.voice_input, str):
            user_context_note = f"User's context: '{req.voice_input[:200]}' - PRIORITIZE this information."
        
        prompt = f"""You are an intelligent assistant explaining a missed call to an Indian user with strong context.

Phone number: {req.phone_number}
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
   - TAKE ACTION NOW (if requires immediate step like filling form)
4. **Why this action** - Based on context provided

User context is the primary signal - use it to guide your recommendation.
Respond in {req.user_language or 'en'} (use Hinglish if Hindi requested).
Make your recommended action BOLD and prominent."""

    import concurrent.futures
    
    def call_ai_api():
        """Try Gemini first (free), then OpenAI with proper error handling"""
        api_errors = []
        user_lang = req.user_language or "en"
        
        # Try Gemini first
        if GEMINI_AVAILABLE:
            try:
                logger.info("Attempting Gemini API call...")
                result = call_gemini_api(prompt, user_lang)
                logger.info("Gemini API successful!")
                return result
            except Exception as gemini_err:
                logger.warning(f"Gemini API failed: {str(gemini_err)}")
                api_errors.append(f"Gemini: {str(gemini_err)}")
        
        # Fallback to OpenAI
        if OPENAI_AVAILABLE and openai.api_key:
            try:
                logger.info("Attempting OpenAI API call...")
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that explains missed calls in a clear, honest way. Never hallucinate. If context is insufficient, say so clearly. Be respectful and concise."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    timeout=10
                )
                result = response.choices[0].message["content"].strip()
                logger.info("OpenAI API successful!")
                return result
            except Exception as openai_err:
                logger.warning(f"OpenAI API failed: {str(openai_err)}")
                api_errors.append(f"OpenAI: {str(openai_err)}")
        
        # If both fail, raise error with details
        error_msg = "All AI APIs failed: " + " | ".join(api_errors) if api_errors else "No AI API available"
        logger.error(error_msg)
        raise Exception(error_msg)

    try:
        # Execute with timeout using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(call_ai_api)
            explanation = future.result(timeout=15)  # 15 second timeout
        
        # Prepare SMS content for response
        sms_response = None
        if sms_content:
            sms_response = [sms['content'] for sms in sms_content]
        
        # Extract suggested action from explanation
        suggested_action = "Check your recent messages"
        if "call back" in explanation.lower():
            suggested_action = "Call back immediately"
        elif "ignore" in explanation.lower():
            suggested_action = "Safe to ignore"
        elif "follow up" in explanation.lower():
            suggested_action = "Follow up with caller"
        
        return {
            "explanation": explanation,
            "state": state,
            "caller_info": {
                "label": enriched_data.get('caller_label'),
                "category": enriched_data.get('category', 'unknown'),
                "is_known": enriched_data.get('is_known', False),
                "description": enriched_data.get('description')
            },
            "suggested_action": suggested_action,
            "disclaimer": "This is an AI-generated explanation based on available context.",
            "metadata": enriched_data,
            "sms_content": sms_response
        }
    except Exception as e:
        import traceback
        logger.error(f"API Error: {str(e)}")
        logger.debug(traceback.format_exc())
        
        # Return the correct state even when API fails
        fallback_explanation = "Unable to generate AI explanation due to API error. Please try again later."
        if state == "STRONG_CONTEXT":
            fallback_explanation = f"This appears to be a {enriched_data.get('caller_label', 'business')} call. Based on available context, this might be important."
        elif state == "WEAK_CONTEXT":
            fallback_explanation = f"This might be a {enriched_data.get('caller_label', 'caller')}. Limited context available."
        
        sms_response = None
        if sms_content:
            sms_response = [sms['content'] for sms in sms_content]
        
        return {
            "explanation": fallback_explanation,
            "state": state,
            "caller_info": {
                "label": enriched_data.get('caller_label'),
                "category": enriched_data.get('category', 'unknown'),
                "is_known": enriched_data.get('is_known', False)
            },
            "suggested_action": "Check your recent messages or callback",
            "error": str(e),
            "disclaimer": "AI explanation unavailable. This is a fallback response based on available context.",
            "metadata": enriched_data,
            "sms_content": sms_response
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/speech_to_text")
async def speech_to_text(file: UploadFile = File(...)):
    """Convert speech audio to text"""
    try:
        # Read the uploaded file
        audio_bytes = await file.read()
        
        # Save to temporary file with original format
        file_extension = file.filename.split('.')[-1].lower() if file.filename else 'wav'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_input:
            temp_input.write(audio_bytes)
            temp_input.flush()
            temp_input_path = temp_input.name
        
        try:
            # Convert to WAV using pydub
            audio = AudioSegment.from_file(temp_input_path)
            
            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_wav:
                wav_path = temp_wav.name
            
            audio.export(wav_path, format='wav')
            
            # Perform speech recognition
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data)
                except sr.UnknownValueError:
                    return {"error": "Could not understand audio"}
                except sr.RequestError as e:
                    return {"error": f"Could not request results from speech recognition service; {e}"}
            
            # Clean up temporary files
            try:
                os.remove(temp_input_path)
                os.remove(wav_path)
            except:
                pass
                
            return {"text": text}
        except Exception as e:
            # Clean up if conversion fails
            try:
                os.remove(temp_input_path)
            except:
                pass
            raise e
    except Exception as e:
        return {"error": str(e)}

@app.post("/analyze_sms")
async def analyze_sms_endpoint(request: dict):
    """Endpoint to analyze a specific SMS and provide context"""
    phone_number = request.get("phone_number", "")
    sms_text = request.get("sms_text", "")
    user_language = request.get("user_language", "en")
    
    if not OPENAI_AVAILABLE and not GEMINI_AVAILABLE:
        return {
            "explanation": "SMS analysis unavailable due to missing API configuration. This appears to be a message from " + phone_number + ".",
            "disclaimer": "AI analysis unavailable due to missing API configuration."
        }
    
    prompt = f"""Analyze this SMS message from {phone_number} and explain what the call might be about:
    
    SMS Content: {sms_text}
    
    Provide a clear explanation in simple {user_language} (use Hinglish if Hindi is requested).
    Be concise and helpful for an Indian user."""

    import concurrent.futures
    
    def call_ai_api():
        """Try OpenAI first, then Gemini for SMS analysis"""
        if OPENAI_AVAILABLE:
            print(f"DEBUG: Making SMS API call with key: {openai.api_key[:10]}...")  # Debug log
            print(f"DEBUG: SMS Prompt length: {len(prompt)}")  # Debug log
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes SMS messages and explains potential call reasons. Never hallucinate. Be respectful and concise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=80,
                timeout=10
            )
            return response.choices[0].message["content"].strip()
        elif GEMINI_AVAILABLE:
            print(f"DEBUG: Making Gemini SMS API call")  # Debug log
            return call_gemini_api(prompt, user_language)
        else:
            raise Exception("No AI API available")

    try:
        # Execute with timeout using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(call_ai_api)
            explanation = future.result(timeout=15)  # 15 second timeout
        
        return {
            "explanation": explanation,
            "disclaimer": "This is an AI-generated explanation based on the SMS content."
        }
    except Exception as e:
        import traceback
        print(f"API Error: {str(e)}")
        print(traceback.format_exc())  # Print full traceback for debugging
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
