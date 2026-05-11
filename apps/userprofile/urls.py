from django.urls import path

from . import views

urlpatterns = [
    path('me/', views.MyProfileView.as_view()),
    path('me/password/', views.ChangePasswordView.as_view()),
    path('me/deactivate/', views.DeactivateAccountView.as_view()),
    # path('email-otp/', views.SendOTPView.as_view()),
    # path('email-verification/', views.VerifyEmailView.as_view()),
    path('admin/users/', views.AdminUserListView.as_view()),
    path('admin/users/<uuid:user_id>/role/', views.AdminUserRoleView.as_view()),
]
