from rest_framework.permissions import BasePermission

from .models import Organization, OrganizationMembership, User


def has_organization_access(user, organization, managers_only=False):
    if not user.is_authenticated or user.role != User.Role.EMPLOYER:
        return False
    if organization.owner_id == user.pk:
        return True
    memberships = OrganizationMembership.objects.filter(user=user, organization=organization)
    if managers_only:
        memberships = memberships.filter(role=OrganizationMembership.Role.MANAGER)
    return memberships.exists()


def can_manage_organization(user, organization):
    return has_organization_access(user, organization, managers_only=True)


class IsModeratorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.MODERATOR, User.Role.ADMIN)
        )


class IsCandidate(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role == User.Role.CANDIDATE)


class IsEmployer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role == User.Role.EMPLOYER)


def user_can_view_resume(user, profile):
    if not user.is_authenticated:
        return profile.resume_visibility == profile.ResumeVisibility.PUBLIC
    if profile.user_id == user.pk:
        return True
    if profile.resume_visibility == profile.ResumeVisibility.PUBLIC:
        return True
    if profile.resume_visibility != profile.ResumeVisibility.AFTER_APPLICATION:
        return False
    return profile.applications.filter(vacancy__organization__memberships__user=user).exists() or (
        profile.applications.filter(vacancy__organization__owner=user).exists()
    )
