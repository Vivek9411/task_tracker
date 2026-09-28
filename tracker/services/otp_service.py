import secrets
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from tracker.models import EmailOTP

RATE_LIMIT_SECONDS = 60
DEFAULT_EXPIRY_MINUTES = 10

def mask_email(email: str) -> str:
    """Masks an email for safe display, e.g. jo***e@example.com"""
    if not email or '@' not in email:
        return '***'
    local_part, domain = email.split('@', 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + '***'
    else:
        masked_local = local_part[0] + '***' + local_part[-1]
    return f"{masked_local}@{domain}"


def generate_otp(email: str, purpose: str = 'PASSWORDLESS', user=None, expiry_minutes: int = DEFAULT_EXPIRY_MINUTES):
    """
    Generates and emails a 6-digit OTP code.
    Enforces a 60-second cooldown rate limit.
    """
    email_clean = email.strip().lower()

    # Rate limiting: Check if an OTP was recently generated
    recent_otp = EmailOTP.objects.filter(
        email__iexact=email_clean,
        purpose=purpose,
        created_at__gte=timezone.now() - timedelta(seconds=RATE_LIMIT_SECONDS)
    ).first()

    if recent_otp:
        remaining_seconds = int(RATE_LIMIT_SECONDS - (timezone.now() - recent_otp.created_at).total_seconds())
        return None, f"Please wait {max(1, remaining_seconds)} seconds before requesting a new code."

    # Invalidate previous unused OTPs for this email and purpose
    EmailOTP.objects.filter(
        email__iexact=email_clean,
        purpose=purpose,
        is_used=False
    ).update(is_used=True)

    # Cryptographically secure 6-digit code (100000 - 999999)
    otp_code = str(secrets.randbelow(900000) + 100000)
    expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

    otp_record = EmailOTP.objects.create(
        user=user,
        email=email_clean,
        otp_code=otp_code,
        purpose=purpose,
        expires_at=expires_at
    )

    # Determine human-friendly purpose wording
    purpose_titles = {
        'PASSWORDLESS': 'Sign In Verification Code',
        'LOGIN_2FA': 'Two-Factor Authentication (2FA) Code',
        'PASSWORD_RESET': 'Password Reset Code'
    }
    action_labels = {
        'PASSWORDLESS': 'sign in to your Nebula Planner account',
        'LOGIN_2FA': 'complete your two-factor login',
        'PASSWORD_RESET': 'reset your Nebula Planner password'
    }

    title = purpose_titles.get(purpose, 'Verification Code')
    action = action_labels.get(purpose, 'verify your account')

    subject = f"{title}: {otp_code} - Nebula Planner"
    
    plain_message = (
        f"Hello,\n\n"
        f"Your verification code to {action} is: {otp_code}\n\n"
        f"This code will expire in {expiry_minutes} minutes.\n"
        f"If you did not request this code, you can safely ignore this email.\n\n"
        f"— Nebula Planner Team"
    )

    html_message = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #0f172a; margin: 0; font-size: 22px; font-weight: 700;">Nebula Planner</h2>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">{title}</p>
        </div>
        <div style="background: #f8fafc; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
            <p style="color: #475569; font-size: 14px; margin: 0 0 12px 0;">Use the 6-digit code below to {action}:</p>
            <div style="font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #0284c7; background: #ffffff; padding: 12px 24px; border-radius: 8px; display: inline-block; border: 1px dashed #cbd5e1;">
                {otp_code}
            </div>
            <p style="color: #94a3b8; font-size: 13px; margin: 16px 0 0 0;">Expires in <strong>{expiry_minutes} minutes</strong></p>
        </div>
        <p style="color: #64748b; font-size: 12px; line-height: 1.5; margin: 0; text-align: center;">
            If you did not make this request, someone may have entered your email address by mistake. Your account is safe and no action is required.
        </p>
    </div>
    """

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Nebula Planner <noreply@nebulaplanner.com>')

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[email_clean],
            html_message=html_message,
            fail_silently=False
        )
    except Exception as exc:
        # If email delivery fails, log it and return error
        return None, f"Failed to send email: {str(exc)}"

    return otp_record, None


def verify_otp(email: str, otp_code: str, purpose: str):
    """
    Verifies a 6-digit OTP code for a given email and purpose.
    Marks OTP as used upon success.
    Returns (True, otp_record) on success or (False, error_message).
    """
    email_clean = email.strip().lower()
    code_clean = otp_code.strip()

    if not code_clean:
        return False, "OTP code is required."

    otp_record = EmailOTP.objects.filter(
        email__iexact=email_clean,
        otp_code=code_clean,
        purpose=purpose,
        is_used=False
    ).order_by('-created_at').first()

    if not otp_record:
        return False, "Invalid verification code. Please check and try again."

    if not otp_record.is_valid():
        return False, "This verification code has expired. Please request a new one."

    # Mark as used
    otp_record.is_used = True
    otp_record.save()

    return True, otp_record
