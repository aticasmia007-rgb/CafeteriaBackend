from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CafeteriaUser
from .services import send_otp_email, verify_otp

BASE = '/api/userauth'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email='user@test.com', name='Test User', password='pass1234', **kwargs):
    return CafeteriaUser.objects.create_user(email=email, name=name, password=password, **kwargs)


def bearer(user):
    return f'Bearer {RefreshToken.for_user(user).access_token}'


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class CafeteriaUserModelTest(TestCase):

    def test_email_is_username_field(self):
        self.assertEqual(CafeteriaUser.USERNAME_FIELD, 'email')

    def test_default_role_is_client(self):
        self.assertEqual(make_user().role, CafeteriaUser.Role.CLIENT)

    def test_is_staff_false_for_client(self):
        self.assertFalse(make_user().is_staff)

    def test_is_staff_true_for_staff_role(self):
        u = make_user()
        u.role = CafeteriaUser.Role.STAFF
        self.assertTrue(u.is_staff)

    def test_is_staff_true_for_admin_role(self):
        u = make_user()
        u.role = CafeteriaUser.Role.ADMIN
        self.assertTrue(u.is_staff)

    def test_default_auth_provider_is_inhouse(self):
        self.assertEqual(make_user().auth_provider, CafeteriaUser.AuthProvider.INHOUSE)

    def test_email_not_verified_by_default(self):
        self.assertFalse(make_user().email_verified)

    def test_is_active_by_default(self):
        self.assertTrue(make_user().is_active)

    def test_str_returns_email(self):
        self.assertEqual(str(make_user(email='hello@test.com')), 'hello@test.com')

    def test_google_user_has_no_usable_password(self):
        u = CafeteriaUser.objects.create_user(
            email='g@test.com', name='G',
            auth_provider=CafeteriaUser.AuthProvider.GOOGLE,
        )
        self.assertFalse(u.has_usable_password())

    def test_uuid_primary_key(self):
        import uuid
        u = make_user(email='uuid@test.com')
        self.assertIsInstance(u.id, uuid.UUID)


# ---------------------------------------------------------------------------
# OTP service
# ---------------------------------------------------------------------------

class OTPServiceTest(TestCase):

    def setUp(self):
        self.user = make_user(email='otp@test.com')

    @patch('apps.userauth.services.send_mail')
    def test_send_otp_sets_6_digit_code(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.assertEqual(len(self.user.otp_code), 6)
        self.assertTrue(self.user.otp_code.isdigit())

    @patch('apps.userauth.services.send_mail')
    def test_send_otp_sets_timestamp(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.otp_created_at)

    @patch('apps.userauth.services.send_mail')
    def test_send_otp_calls_send_mail_with_user_email(self, mock_mail):
        send_otp_email(self.user)
        mock_mail.assert_called_once()
        self.assertIn(self.user.email, mock_mail.call_args[1]['recipient_list'])

    @patch('apps.userauth.services.send_mail')
    def test_verify_correct_code_returns_true(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.assertTrue(verify_otp(self.user, self.user.otp_code))

    @patch('apps.userauth.services.send_mail')
    def test_verify_marks_email_verified(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        verify_otp(self.user, self.user.otp_code)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    @patch('apps.userauth.services.send_mail')
    def test_verify_clears_otp_fields_after_success(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        verify_otp(self.user, self.user.otp_code)
        self.user.refresh_from_db()
        self.assertEqual(self.user.otp_code, '')
        self.assertIsNone(self.user.otp_created_at)

    @patch('apps.userauth.services.send_mail')
    def test_verify_wrong_code_returns_false(self, mock_mail):
        send_otp_email(self.user)
        self.assertFalse(verify_otp(self.user, '000000'))

    @patch('apps.userauth.services.send_mail')
    def test_verify_expired_code_returns_false(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.user.otp_created_at = timezone.now() - timedelta(minutes=11)
        self.user.save(update_fields=['otp_created_at'])
        self.assertFalse(verify_otp(self.user, self.user.otp_code))

    @patch('apps.userauth.services.send_mail')
    def test_verify_skip_email_verified_flag(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        verify_otp(self.user, self.user.otp_code, mark_email_verified=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_verify_no_otp_set_returns_false(self):
        self.assertFalse(verify_otp(self.user, '123456'))


# ---------------------------------------------------------------------------
# POST /api/userauth/login/
# ---------------------------------------------------------------------------

class LoginViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/login/'
        self.user = make_user(email='login@test.com', password='pass1234')

    def test_success_returns_200_and_status_00(self):
        res = self.client.post(self.url, {'email': 'login@test.com', 'password': 'pass1234'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')

    def test_success_includes_access_and_refresh_tokens(self):
        res = self.client.post(self.url, {'email': 'login@test.com', 'password': 'pass1234'})
        self.assertIn('access_token', res.data)
        self.assertIn('refresh_token', res.data)

    def test_success_user_object_has_required_fields(self):
        res = self.client.post(self.url, {'email': 'login@test.com', 'password': 'pass1234'})
        user_data = res.data['user']
        for field in ['user_id', 'name', 'email', 'role', 'auth_provider', 'email_verified', 'is_active']:
            self.assertIn(field, user_data, msg=f'Missing field: {field}')

    def test_wrong_password_returns_401_status_03(self):
        res = self.client.post(self.url, {'email': 'login@test.com', 'password': 'wrong'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.data['status'], '03')

    def test_unknown_email_returns_401(self):
        res = self.client.post(self.url, {'email': 'nobody@test.com', 'password': 'pass1234'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_returns_401(self):
        self.user.is_active = False
        self.user.save()
        res = self.client.post(self.url, {'email': 'login@test.com', 'password': 'pass1234'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_password_returns_401(self):
        res = self.client.post(self.url, {'email': 'login@test.com'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_body_returns_401(self):
        res = self.client.post(self.url, {})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# POST /api/userauth/register/
# ---------------------------------------------------------------------------

class RegisterViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/register/'
        self.valid_payload = {'email': 'new@test.com', 'password': 'pass1234', 'name': 'New User'}

    @patch('apps.userauth.views.send_otp_email')
    def test_success_returns_201_status_00(self, _):
        res = self.client.post(self.url, self.valid_payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], '00')

    @patch('apps.userauth.views.send_otp_email')
    def test_success_creates_user_in_db(self, _):
        self.client.post(self.url, self.valid_payload)
        self.assertTrue(CafeteriaUser.objects.filter(email='new@test.com').exists())

    @patch('apps.userauth.views.send_otp_email')
    def test_success_sends_otp(self, mock_otp):
        self.client.post(self.url, self.valid_payload)
        mock_otp.assert_called_once()

    @patch('apps.userauth.views.send_otp_email')
    def test_success_includes_tokens(self, _):
        res = self.client.post(self.url, self.valid_payload)
        self.assertIn('access_token', res.data)
        self.assertIn('refresh_token', res.data)

    @patch('apps.userauth.views.send_otp_email')
    def test_duplicate_email_returns_422_status_06(self, _):
        make_user(email='dup@test.com')
        res = self.client.post(self.url, {'email': 'dup@test.com', 'password': 'pass1234', 'name': 'Dup'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(res.data['status'], '06')

    @patch('apps.userauth.views.send_otp_email')
    def test_password_too_short_returns_422(self, _):
        res = self.client.post(self.url, {'email': 'pw@test.com', 'password': '123', 'name': 'Short'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    @patch('apps.userauth.views.send_otp_email')
    def test_missing_name_returns_422(self, _):
        res = self.client.post(self.url, {'email': 'noname@test.com', 'password': 'pass1234'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    @patch('apps.userauth.views.send_otp_email')
    def test_invalid_email_format_returns_422(self, _):
        res = self.client.post(self.url, {'email': 'not-an-email', 'password': 'pass1234', 'name': 'X'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    @patch('apps.userauth.views.send_otp_email')
    def test_new_user_has_client_role(self, _):
        self.client.post(self.url, self.valid_payload)
        user = CafeteriaUser.objects.get(email='new@test.com')
        self.assertEqual(user.role, CafeteriaUser.Role.CLIENT)

    @patch('apps.userauth.views.send_otp_email')
    def test_new_user_email_not_verified(self, _):
        self.client.post(self.url, self.valid_payload)
        user = CafeteriaUser.objects.get(email='new@test.com')
        self.assertFalse(user.email_verified)


# ---------------------------------------------------------------------------
# POST /api/userauth/logout/
# ---------------------------------------------------------------------------

class LogoutViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/logout/'
        self.user = make_user(email='logout@test.com')
        self.refresh = RefreshToken.for_user(self.user)

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')

    def test_success_returns_200_status_00(self):
        self._auth()
        res = self.client.post(self.url, {'refresh_token': str(self.refresh)})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')

    def test_requires_authentication(self):
        res = self.client.post(self.url, {'refresh_token': str(self.refresh)})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_already_blacklisted_token_still_returns_200(self):
        self._auth()
        self.client.post(self.url, {'refresh_token': str(self.refresh)})
        res = self.client.post(self.url, {'refresh_token': str(self.refresh)})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_no_refresh_token_body_still_returns_200(self):
        self._auth()
        res = self.client.post(self.url, {})
        self.assertEqual(res.status_code, status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# GET /api/userauth/email-otp/
# ---------------------------------------------------------------------------

class SendOTPViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/email-otp/'
        self.user = make_user(email='sendotp@test.com')

    def test_requires_authentication(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.userauth.views.send_otp_email')
    def test_returns_200_status_00(self, mock_otp):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')

    @patch('apps.userauth.views.send_otp_email')
    def test_calls_send_otp_for_authenticated_user(self, mock_otp):
        self.client.force_authenticate(user=self.user)
        self.client.get(self.url)
        mock_otp.assert_called_once_with(self.user)


# ---------------------------------------------------------------------------
# POST /api/userauth/email-verification/
# ---------------------------------------------------------------------------

class VerifyEmailViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/email-verification/'
        self.user = make_user(email='verify@test.com')

    def test_requires_authentication(self):
        res = self.client.post(self.url, {'otp': '123456'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.userauth.services.send_mail')
    def test_correct_otp_returns_200(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {'otp': self.user.otp_code})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')

    @patch('apps.userauth.services.send_mail')
    def test_correct_otp_marks_user_verified(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        self.client.post(self.url, {'otp': self.user.otp_code})
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_wrong_otp_returns_422_status_06(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {'otp': '000000'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(res.data['status'], '06')

    def test_otp_too_short_returns_422(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {'otp': '12'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_missing_otp_returns_422(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.url, {})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


# ---------------------------------------------------------------------------
# POST /api/userauth/password-recovery/
# ---------------------------------------------------------------------------

class PasswordRecoveryViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/password-recovery/'

    @patch('apps.userauth.views.send_otp_email')
    def test_known_email_returns_200_and_sends_otp(self, mock_otp):
        make_user(email='recovery@test.com')
        res = self.client.post(self.url, {'email': 'recovery@test.com'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')
        mock_otp.assert_called_once()

    @patch('apps.userauth.views.send_otp_email')
    def test_unknown_email_returns_200_without_sending_otp(self, mock_otp):
        res = self.client.post(self.url, {'email': 'nobody@test.com'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')
        mock_otp.assert_not_called()

    @patch('apps.userauth.views.send_otp_email')
    def test_google_user_email_not_triggered(self, mock_otp):
        CafeteriaUser.objects.create_user(
            email='g@test.com', name='G',
            auth_provider=CafeteriaUser.AuthProvider.GOOGLE,
        )
        res = self.client.post(self.url, {'email': 'g@test.com'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_otp.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/userauth/password-recovery/confirm/
# ---------------------------------------------------------------------------

class PasswordRecoveryConfirmViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/password-recovery/confirm/'
        self.user = make_user(email='confirm@test.com', password='oldpass1')

    @patch('apps.userauth.services.send_mail')
    def test_correct_otp_resets_password(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        res = self.client.post(self.url, {
            'email': 'confirm@test.com',
            'otp': self.user.otp_code,
            'new_password': 'newpass1234',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass1234'))

    @patch('apps.userauth.services.send_mail')
    def test_correct_otp_does_not_mark_email_verified(self, mock_mail):
        send_otp_email(self.user)
        self.user.refresh_from_db()
        self.client.post(self.url, {
            'email': 'confirm@test.com',
            'otp': self.user.otp_code,
            'new_password': 'newpass1234',
        })
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    @patch('apps.userauth.services.send_mail')
    def test_wrong_otp_returns_422_status_06(self, mock_mail):
        send_otp_email(self.user)
        res = self.client.post(self.url, {
            'email': 'confirm@test.com',
            'otp': '000000',
            'new_password': 'newpass1234',
        })
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(res.data['status'], '06')

    def test_unknown_email_returns_422(self):
        res = self.client.post(self.url, {
            'email': 'nobody@test.com',
            'otp': '123456',
            'new_password': 'newpass1234',
        })
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_missing_fields_returns_422(self):
        res = self.client.post(self.url, {'email': 'confirm@test.com'})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_short_new_password_returns_422(self):
        res = self.client.post(self.url, {
            'email': 'confirm@test.com',
            'otp': '123456',
            'new_password': '123',
        })
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


# ---------------------------------------------------------------------------
# POST /api/userauth/google/
# ---------------------------------------------------------------------------

class GoogleLoginViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = f'{BASE}/google/'
        self.google_payload = {
            'email': 'google@test.com',
            'name': 'Google User',
            'picture': 'https://photo.url',
            'email_verified': True,
        }

    @patch('apps.userauth.views.validate_google_token')
    def test_valid_token_creates_user_and_returns_200(self, mock_validate):
        mock_validate.return_value = self.google_payload
        res = self.client.post(self.url, {'token': 'fake-token'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], '00')
        self.assertTrue(CafeteriaUser.objects.filter(email='google@test.com').exists())

    @patch('apps.userauth.views.validate_google_token')
    def test_valid_token_returns_jwt_tokens(self, mock_validate):
        mock_validate.return_value = self.google_payload
        res = self.client.post(self.url, {'token': 'fake-token'})
        self.assertIn('access_token', res.data)
        self.assertIn('refresh_token', res.data)

    @patch('apps.userauth.views.validate_google_token')
    def test_creates_user_with_google_provider(self, mock_validate):
        mock_validate.return_value = self.google_payload
        self.client.post(self.url, {'token': 'fake-token'})
        user = CafeteriaUser.objects.get(email='google@test.com')
        self.assertEqual(user.auth_provider, CafeteriaUser.AuthProvider.GOOGLE)

    @patch('apps.userauth.views.validate_google_token')
    def test_existing_google_user_returns_200(self, mock_validate):
        CafeteriaUser.objects.create_user(
            email='existing@test.com', name='Existing',
            auth_provider=CafeteriaUser.AuthProvider.GOOGLE,
        )
        mock_validate.return_value = {**self.google_payload, 'email': 'existing@test.com'}
        res = self.client.post(self.url, {'token': 'fake-token'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch('apps.userauth.views.validate_google_token')
    def test_email_conflict_with_inhouse_user_returns_401(self, mock_validate):
        make_user(email='inhouse@test.com', name='In-house')
        mock_validate.return_value = {**self.google_payload, 'email': 'inhouse@test.com'}
        res = self.client.post(self.url, {'token': 'fake-token'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.data['status'], '03')

    @patch('apps.userauth.views.validate_google_token')
    def test_inactive_google_user_returns_403(self, mock_validate):
        CafeteriaUser.objects.create_user(
            email='inactive@test.com', name='Inactive',
            auth_provider=CafeteriaUser.AuthProvider.GOOGLE,
            is_active=False,
        )
        mock_validate.return_value = {**self.google_payload, 'email': 'inactive@test.com'}
        res = self.client.post(self.url, {'token': 'fake-token'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data['status'], '04')

    @patch('apps.userauth.views.validate_google_token')
    def test_invalid_google_token_returns_401_status_03(self, mock_validate):
        mock_validate.side_effect = ValueError('Token de Google inválido.')
        res = self.client.post(self.url, {'token': 'bad-token'})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.data['status'], '03')

    def test_missing_token_field_returns_422(self):
        res = self.client.post(self.url, {})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(res.data['status'], '06')
