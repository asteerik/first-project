from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import CandidateProfile, Organization, OrganizationMembership, User
from .permissions import can_manage_organization, has_organization_access
from .serializers import (
    CandidateProfileSerializer,
    OrganizationMembershipSerializer,
    OrganizationSerializer,
    PublicOrganizationSerializer,
    RegistrationSerializer,
    UserSerializer,
)


class ScopedAnonRateThrottle(AnonRateThrottle):
    scope = "registration"


class RegistrationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedAnonRateThrottle]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError as exc:
            raise ValidationError({"email": "Пользователь с такой почтой уже зарегистрирован."}) from exc
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class LoginSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    serializer_class = LoginSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"refresh": "Передайте refresh-токен."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            return Response({"detail": "Недействительный или просроченный токен."}, status=400)
        if str(token.get("user_id")) != str(request.user.pk):
            raise PermissionDenied("Нельзя завершить сессию другого пользователя.")
        token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        if self.request.user.role != User.Role.CANDIDATE:
            raise PermissionDenied("Профиль соискателя доступен только соискателю.")
        return get_object_or_404(CandidateProfile, user=self.request.user)


class OrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role != User.Role.EMPLOYER:
            return Organization.objects.none()
        return Organization.objects.filter(
            memberships__user=self.request.user
        ).distinct() | Organization.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.EMPLOYER:
            raise PermissionDenied("Создавать организации может только работодатель.")
        organization = serializer.save(owner=self.request.user)
        OrganizationMembership.objects.create(
            organization=organization,
            user=self.request.user,
            role=OrganizationMembership.Role.MANAGER,
        )


class OrganizationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_queryset(self):
        return Organization.objects.all()

    def get_object(self):
        organization = super().get_object()
        if not has_organization_access(self.request.user, organization):
            raise PermissionDenied("Нет доступа к этой организации.")
        if self.request.method != "GET" and not can_manage_organization(self.request.user, organization):
            raise PermissionDenied("Изменять организацию может только владелец или управляющий.")
        return organization

    def perform_update(self, serializer):
        organization = serializer.save(
            verification_status=Organization.VerificationStatus.PENDING,
            verification_note="",
            verified_at=None,
        )
        organization.vacancies.filter(status="approved").update(
            status="pending",
            published_at=None,
            updated_at=timezone.now(),
        )


class OrganizationMemberListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs["organization_id"])

    def get_queryset(self):
        organization = self.get_organization()
        if not can_manage_organization(self.request.user, organization):
            raise PermissionDenied("Управлять участниками может только владелец или управляющий.")
        return OrganizationMembership.objects.filter(organization=organization).select_related("user")

    def perform_create(self, serializer):
        organization = self.get_organization()
        if not can_manage_organization(self.request.user, organization):
            raise PermissionDenied("Управлять участниками может только владелец или управляющий.")
        try:
            with transaction.atomic():
                serializer.save(organization=organization)
        except IntegrityError as exc:
            raise ValidationError("Этот пользователь уже добавлен в организацию.") from exc


class OrganizationMemberDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, organization_id, membership_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        if not can_manage_organization(request.user, organization):
            raise PermissionDenied("Управлять участниками может только владелец или управляющий.")
        membership = get_object_or_404(
            OrganizationMembership,
            pk=membership_id,
            organization=organization,
        )
        if membership.user_id == organization.owner_id:
            raise PermissionDenied("Нельзя удалить владельца организации из её участников.")
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
