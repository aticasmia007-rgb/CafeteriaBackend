import random
import string
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests


OTP_EXPIRY_SECONDS = 10 * 60  # 10 minutes


def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(user):
    otp = _generate_otp()
    user.otp_code = otp
    user.otp_created_at = timezone.now()
    user.save(update_fields=['otp_code', 'otp_created_at'])
    send_mail(
        subject='Código de verificación — Cafetería',
        message=f'Tu código de verificación es: {otp}\nCaduca en 10 minutos.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def verify_otp(user, code, mark_email_verified=True):
    if not user.otp_code or not user.otp_created_at:
        return False
    elapsed = (timezone.now() - user.otp_created_at).total_seconds()
    if elapsed > OTP_EXPIRY_SECONDS or user.otp_code != code:
        return False
    update_fields = ['otp_code', 'otp_created_at']
    user.otp_code = ''
    user.otp_created_at = None
    if mark_email_verified:
        user.email_verified = True
        update_fields.append('email_verified')
    user.save(update_fields=update_fields)
    return True


def validate_google_token(code):
    """Validates a Google ID token. Returns payload dict or raises ValueError."""
    try:
        print('Google token response:', settings.GOOGLE_CLIENT_ID, code)  # Debug log
        token_response = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": "postmessage",  # Importante para popup
            "grant_type": "authorization_code",
        })

        tokens = token_response.json()
        id_token_jwt = tokens["id_token"]  
        
        
        payload = id_token.verify_oauth2_token(
            id_token_jwt,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        print('Google token payload:', payload)  # Debug log
        return payload
    except Exception as exc:
        print('Google token validation error:', exc)  # Debug log
        raise ValueError('Token de Google inválido.') from exc
