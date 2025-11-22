import requests
from django.conf import settings

def send_sms(phone, message):
    """
    Send SMS using BulkSMS South Africa
    You need to sign up at https://www.bulksms.com/za/ and get API credentials
    """
    
    # BulkSMS API configuration
    BULKSMS_USERNAME = getattr(settings, 'BULKSMS_USERNAME', '')
    BULKSMS_PASSWORD = getattr(settings, 'BULKSMS_PASSWORD', '')
    
    if not BULKSMS_USERNAME or not BULKSMS_PASSWORD:
        print(f"SMS not configured. Would send to {phone}: {message}")
        return False
    
    try:
        url = 'https://api.bulksms.com/v1/messages'
        auth = (BULKSMS_USERNAME, BULKSMS_PASSWORD)
        
        # Ensure phone number is in international format
        if not phone.startswith('+'):
            phone = '+27' + phone.lstrip('0')
        
        data = {
            'to': phone,
            'body': message,
        }
        
        response = requests.post(url, json=data, auth=auth)
        
        if response.status_code == 201:
            return True
        else:
            print(f"SMS failed: {response.text}")
            return False
    
    except Exception as e:
        print(f"SMS error: {str(e)}")
        return False


def send_booking_confirmation(booking):
    """Send booking confirmation SMS"""
    phone = booking.get_client_phone()
    name = booking.get_client_name()
    
    message = f"Hi {name}, your appointment with {booking.barber.username} is confirmed for {booking.appointment_date} at {booking.appointment_time.strftime('%H:%M')}. To cancel: {settings.SITE_URL}/cancel/{booking.cancellation_token}"
    
    if send_sms(phone, message):
        booking.sms_confirmation_sent = True
        booking.save()
        return True
    return False


def send_booking_reminder(booking):
    """Send 10-minute reminder SMS"""
    phone = booking.get_client_phone()
    name = booking.get_client_name()
    
    message = f"Hi {name}, your appointment with {booking.barber.username} starts in 10 minutes at {booking.appointment_time.strftime('%H:%M')}. See you soon!"
    
    if send_sms(phone, message):
        booking.sms_reminder_sent = True
        booking.save()
        return True
    return False