import requests
import re
import logging
import dns.resolver
import smtplib
import socket

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


def verify_email_deliverable(email):
    """
    Verifies if an email address is likely deliverable by:
    1. Validating email format
    2. Checking if the domain has valid MX records
    3. Optionally attempting SMTP verification
    
    Returns: (is_valid, error_message)
    """
    if not email:
        return False, "Email address is required."
    
    # Basic format validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format."
    
    # Extract domain
    try:
        domain = email.split('@')[1]
    except IndexError:
        return False, "Invalid email format."
    
    # Check MX records
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        if not mx_records:
            return False, f"The domain '{domain}' does not accept emails."
        
        # Get the primary MX server
        mx_host = str(mx_records[0].exchange).rstrip('.')
        
        # Try to connect to the SMTP server to verify it's accepting connections
        try:
            smtp = smtplib.SMTP(timeout=10)
            smtp.connect(mx_host, 25)
            smtp.helo('connect2give.local')
            
            # Try MAIL FROM and RCPT TO to verify the email exists
            # Note: Many servers don't allow this check (anti-spam)
            smtp.mail('noreply@connect2give.local')
            code, message = smtp.rcpt(email)
            smtp.quit()
            
            # 250 = OK, 251 = User not local but will forward
            if code in [250, 251]:
                return True, None
            elif code == 550:  # User doesn't exist
                return False, f"The email address '{email}' does not exist on this server."
            else:
                # Can't verify, but MX exists - assume valid
                return True, None
                
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, 
                socket.timeout, socket.error, OSError) as e:
            # SMTP check failed but MX records exist - domain is valid
            # Many servers block SMTP verification, so we'll trust MX records
            logger.info(f"SMTP verification skipped for {email}: {e}")
            return True, None
            
    except dns.resolver.NXDOMAIN:
        return False, f"The domain '{domain}' does not exist."
    except dns.resolver.NoAnswer:
        return False, f"The domain '{domain}' does not have email configured."
    except dns.resolver.NoNameservers:
        return False, f"Could not verify the domain '{domain}'. Please check the email address."
    except Exception as e:
        logger.error(f"Email verification error for {email}: {e}")
        # On unexpected errors, still allow - don't block legitimate users
        return True, None


# Verhoeff Algorithm for Aadhar Card Validation
# Aadhar uses Verhoeff checksum - the last digit is a check digit

# Multiplication table for Verhoeff algorithm
VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

# Permutation table for Verhoeff algorithm
VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]

def validate_aadhar_verhoeff(aadhar_number):
    """
    Validates an Aadhar card number using the Verhoeff checksum algorithm.
    
    The Aadhar number is a 12-digit unique identification number where:
    - First digit cannot be 0 or 1
    - Last digit is a check digit calculated using Verhoeff algorithm
    
    Returns: (is_valid, error_message)
    """
    if not aadhar_number:
        return False, "Aadhar number is required."
    
    # Remove any spaces or hyphens
    aadhar_clean = aadhar_number.replace(' ', '').replace('-', '')
    
    # Check if it's exactly 12 digits
    if not aadhar_clean.isdigit():
        return False, "Aadhar number must contain only digits."
    
    if len(aadhar_clean) != 12:
        return False, "Aadhar number must be exactly 12 digits."
    
    # First digit cannot be 0 or 1
    if aadhar_clean[0] in ['0', '1']:
        return False, "Aadhar number cannot start with 0 or 1."
    
    # Verhoeff checksum validation
    c = 0
    reversed_digits = [int(d) for d in reversed(aadhar_clean)]
    
    for i, digit in enumerate(reversed_digits):
        c = VERHOEFF_D[c][VERHOEFF_P[i % 8][digit]]
    
    if c != 0:
        return False, "Invalid Aadhar number. Please check and re-enter."
    
    return True, None
