import re
from typing import List, Dict, Optional
from datetime import datetime

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

# Global instance
sms_handler = SMSHandler()