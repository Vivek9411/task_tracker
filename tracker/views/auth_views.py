import urllib.parse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from tracker.serializers import UserRegisterSerializer, UserSerializer
from tracker.models import UserProfile
from tracker.services.otp_service import generate_otp, verify_otp, mask_email
from tracker.services.google_auth_service import (
    verify_google_credential,
    get_or_create_google_user,
    get_google_oauth_redirect_url,
    exchange_code_for_google_user,
    generate_unique_username,
)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Ensure profile and streak exist
            UserProfile.objects.get_or_create(user=user)
            # Log the user in directly after registration
            login(request, user)
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        
        # Extract the first error message to return a clean string
        error_dict = serializer.errors
        first_field = list(error_dict.keys())[0]
        first_error = error_dict[first_field][0]
        
        if first_field == 'non_field_errors':
            error_message = str(first_error)
        else:
            error_message = f"{first_field.capitalize()}: {first_error}"
            
        return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username_or_email = (request.data.get('username') or '').strip()
        password = request.data.get('password')

        if not username_or_email or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Allow login using email address as username
        user = None
        if '@' in username_or_email:
            matched_user = User.objects.filter(email__iexact=username_or_email).first()
            if matched_user:
                user = authenticate(username=matched_user.username, password=password)
        
        if not user:
            user = authenticate(username=username_or_email, password=password)

        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

        profile, _ = UserProfile.objects.get_or_create(user=user)

        # Check if Two-Factor Authentication (2FA) is enabled for this user
        if profile.is_2fa_enabled and user.email:
            otp_record, err = generate_otp(user.email, purpose='LOGIN_2FA', user=user)
            if err:
                return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)

            # Generate a signed temporary token for 2FA verification step
            session_token = signing.dumps({'user_id': user.id}, salt='2fa-login')
            return Response({
                'requires_2fa': True,
                'session_token': session_token,
                'masked_email': mask_email(user.email),
                'message': f"A 6-digit verification code was sent to {mask_email(user.email)}"
            }, status=status.HTTP_200_OK)

        # Standard direct login
        login(request, user)
        return Response(UserSerializer(user).data)


class Verify2FALoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_token = request.data.get('session_token')
        otp_code = request.data.get('otp_code')

        if not session_token or not otp_code:
            return Response({'error': 'Session token and OTP code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = signing.loads(session_token, salt='2fa-login', max_age=600)
            user_id = payload.get('user_id')
            user = User.objects.get(id=user_id)
        except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
            return Response({'error': 'Verification session expired. Please sign in again.'}, status=status.HTTP_400_BAD_REQUEST)

        valid, msg = verify_otp(user.email, otp_code, purpose='LOGIN_2FA')
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)
        return Response(UserSerializer(user).data)


class SendPasswordlessOTPView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email or '@' not in email:
            return Response({'error': 'Please enter a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        otp_record, err = generate_otp(email, purpose='PASSWORDLESS', user=user)
        if err:
            return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f"Verification code sent to {mask_email(email)}",
            'masked_email': mask_email(email)
        })


class VerifyPasswordlessOTPView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        otp_code = (request.data.get('otp_code') or '').strip()

        if not email or not otp_code:
            return Response({'error': 'Email and verification code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        valid, msg = verify_otp(email, otp_code, purpose='PASSWORDLESS')
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        # Find or create user
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            base_name = email.split('@')[0]
            username = generate_unique_username(base_name)
            user = User.objects.create_user(username=username, email=email)
            user.set_unusable_password()
            user.save()

        UserProfile.objects.get_or_create(user=user)
        login(request, user)
        return Response(UserSerializer(user).data)


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email or '@' not in email:
            return Response({'error': 'Please enter a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({'error': 'No account found with this email address. Please check your email or register.'}, status=status.HTTP_400_BAD_REQUEST)

        otp_record, err = generate_otp(email, purpose='PASSWORD_RESET', user=user)
        if err:
            return Response({'error': err}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f"A 6-digit reset code has been sent to {mask_email(email)}.",
            'masked_email': mask_email(email)
        })


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        otp_code = (request.data.get('otp_code') or '').strip()
        new_password = request.data.get('new_password')

        if not email or not otp_code or not new_password:
            return Response({'error': 'Email, verification code, and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({'error': 'Invalid reset request. Please request a new code.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate password strength
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return Response({'error': ' '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        valid, msg = verify_otp(email, otp_code, purpose='PASSWORD_RESET')
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        # Set new password
        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password has been reset successfully. You may now sign in with your new password.'})


class GoogleAuthView(APIView):
    """
    Accepts Google ID token (credential) from Google Identity Services.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get('credential')
        if not credential:
            return Response({'error': 'Google credential token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        google_data, err = verify_google_credential(credential)
        if err or not google_data:
            return Response({'error': err or 'Google verification failed.'}, status=status.HTTP_400_BAD_REQUEST)

        user, err = get_or_create_google_user(google_data)
        if err or not user:
            return Response({'error': err or 'Failed to link Google account.'}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)
        return Response(UserSerializer(user).data)


class GoogleOAuthRedirectView(APIView):
    """
    Initiates standard OAuth 2.0 authorization redirect to Google.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            redirect_url = get_google_oauth_redirect_url(request)
            return redirect(redirect_url)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GoogleOAuthCallbackView(APIView):
    """
    Handles Google OAuth redirect callback with authorization code.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error or not code:
            err_msg = error or 'Google authorization cancelled.'
            return redirect(f'/login/?error={urllib.parse.quote(err_msg)}')

        user, err = exchange_code_for_google_user(request, code)
        if err or not user:
            return redirect(f'/login/?error={urllib.parse.quote(err or "Google sign in failed")}')

        login(request, user)
        return redirect('/')


class Toggle2FAView(APIView):
    """
    Toggles Two-Factor Authentication for the currently authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        enable = request.data.get('enable')
        if enable is None:
            # Toggle
            profile.is_2fa_enabled = not profile.is_2fa_enabled
        else:
            profile.is_2fa_enabled = bool(enable)

        profile.save()
        return Response({
            'is_2fa_enabled': profile.is_2fa_enabled,
            'message': f"Two-Factor Authentication {'enabled' if profile.is_2fa_enabled else 'disabled'} successfully."
        })


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logout(request)
        return Response({'message': 'Logged out successfully'})


class CurrentUserView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
