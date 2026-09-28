import urllib.parse
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from tracker.models import UserProfile, Streak

try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False


def verify_google_credential(credential_token: str):
    """
    Verifies a Google ID token from Google Identity Services.
    Returns (user_info_dict, error_message).
    """
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
    
    # 1. Try google-auth library if available
    if GOOGLE_AUTH_AVAILABLE and client_id:
        try:
            idinfo = google_id_token.verify_oauth2_token(
                credential_token,
                google_requests.Request(),
                client_id
            )
            return idinfo, None
        except Exception as e:
            # Fall back to tokeninfo endpoint
            pass

    # 2. Tokeninfo verification via Google OAuth2 API
    try:
        resp = requests.get(
            'https://oauth2.googleapis.com/tokeninfo',
            params={'id_token': credential_token},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if client_id and data.get('aud') != client_id:
                return None, "Google token audience mismatch."
            return data, None
        return None, "Invalid Google credential token."
    except Exception as exc:
        return None, f"Google token verification failed: {str(exc)}"


def generate_unique_username(base_name: str) -> str:
    """Generates a unique username from an email prefix or name."""
    clean_base = ''.join(c for c in base_name if c.isalnum() or c in '_-')[:20]
    if not clean_base:
        clean_base = 'user'
    
    candidate = clean_base
    counter = 1
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{clean_base}_{counter}"
        counter += 1
    return candidate


def get_or_create_google_user(google_info: dict):
    """
    Finds or creates a Django User linked to a verified Google account.
    """
    email = (google_info.get('email') or '').strip().lower()
    google_id = str(google_info.get('sub') or '')

    if not email:
        return None, "Google account does not provide an email address."

    # Check if user with this email already exists
    user = User.objects.filter(email__iexact=email).first()

    if not user:
        # Check if user with google_id in profile exists
        profile = UserProfile.objects.filter(google_id=google_id).first()
        if profile:
            user = profile.user

    if not user:
        # Create new user
        suggested_name = google_info.get('name') or email.split('@')[0]
        username = generate_unique_username(suggested_name)
        first_name = google_info.get('given_name', '')
        last_name = google_info.get('family_name', '')

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        user.set_unusable_password()
        user.save()

    # Ensure profile and streak exist
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if google_id and profile.google_id != google_id:
        profile.google_id = google_id
        profile.save()

    user.profile = profile
    Streak.objects.get_or_create(user=user)

    return user, None



def get_google_oauth_redirect_url(request) -> str:
    """
    Constructs Google OAuth 2.0 authorization URL for redirect flow.
    """
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured in settings or .env.")

    redirect_uri = request.build_absolute_uri(reverse('api-google-callback'))
    # Ensure http for localhost or https
    if not request.is_secure() and not redirect_uri.startswith('http://localhost') and not redirect_uri.startswith('http://127.0.0.1'):
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'online',
        'prompt': 'select_account',
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"


def exchange_code_for_google_user(request, code: str):
    """
    Exchanges an OAuth authorization code for Google user details.
    """
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '').strip()
    redirect_uri = request.build_absolute_uri(reverse('api-google-callback'))

    if not client_id or not client_secret:
        return None, "Google OAuth Client ID and Secret must be configured."

    # Exchange code for token
    token_url = 'https://oauth2.googleapis.com/token'
    token_data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    try:
        resp = requests.post(token_url, data=token_data, timeout=10)
        tokens = resp.json()
        if 'error' in tokens:
            return None, tokens.get('error_description') or tokens.get('error')

        # Fetch user info using access token
        access_token = tokens.get('access_token')
        userinfo_resp = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if userinfo_resp.status_code != 200:
            return None, "Failed to retrieve user info from Google."

        user_info = userinfo_resp.json()
        return get_or_create_google_user(user_info)
    except Exception as exc:
        return None, f"Google code exchange failed: {str(exc)}"
