from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    OrganizationDetailView,
    OrganizationListCreateView,
    OrganizationMemberDeleteView,
    OrganizationMemberListCreateView,
    ProfileView,
    RegistrationView,
)

urlpatterns = [
    path("auth/register/", RegistrationView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("organizations/", OrganizationListCreateView.as_view(), name="organizations"),
    path("organizations/<int:pk>/", OrganizationDetailView.as_view(), name="organization_detail"),
    path(
        "organizations/<int:organization_id>/members/",
        OrganizationMemberListCreateView.as_view(),
        name="organization_members",
    ),
    path(
        "organizations/<int:organization_id>/members/<int:membership_id>/",
        OrganizationMemberDeleteView.as_view(),
        name="organization_member_delete",
    ),
]
