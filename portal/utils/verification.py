import requests
import re
import logging

logger = logging.getLogger(__name__)

def verify_fssai(fssai_number):
    """
    Verifies FSSAI license number.
    Note: Real API access is restricted. This is a mock implementation based on the user request 
    example or a simulated check. If a real endpoint handles this without auth, we can try it.
    
    For Hackathon purposes, we will treat valid length and numeric as a basic check,
    or use the endpoint if it works.
    """
    if not fssai_number or not fssai_number.isdigit() or len(fssai_number) != 14:
        return False
        
    try:
        # Real FSSAI API Endpoint
        url = "https://foscos.fssai.gov.in/FOODLICENSE/ShowLicenseDetails"
        payload = {"licenseNo": fssai_number}
        
        # Real call - wrapped in try/except because external APIs might fail/timeout
        # Short timeout to avoid hanging
        response = requests.post(url, data=payload, timeout=5)
        
        if response.status_code == 200 and "License Details" in response.text:
            return True
        
        # If API denies or fails validation
        return False
        
    except Exception as e:
        logger.error(f"FSSAI verification error: {e}")
        # Fail safe
        return False

def validate_ngo_darpan_format(darpan_id):
    """
    Validates the format of NGO Darpan ID.
    Format is typically: AA/YYYY/NNNNNN (2 chars / 4 digits / 6 digits)
    """
    if not darpan_id:
        return False
        
    # Pattern: 2 Uppercase letters / 4 Digits / 6 Digits
    # Example: DL/2021/012345
    pattern = r"^[A-Z]{2}/\d{4}/\d{6}$"
    return bool(re.match(pattern, darpan_id))
