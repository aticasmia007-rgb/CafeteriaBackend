from django.urls import path
from . import views

urlpatterns = [
    path('google/', views.GoogleLoginView.as_view()),
    path('login/', views.LoginView.as_view()),
    path('register/', views.RegisterView.as_view()),
    path('logout/', views.LogoutView.as_view()),
    path('email-otp/', views.SendOTPView.as_view()),
    path('email-verification/', views.VerifyEmailView.as_view()),
    path('password-recovery/', views.PasswordRecoveryView.as_view()),
    path('password-recovery/confirm/', views.PasswordRecoveryConfirmView.as_view()),
]
