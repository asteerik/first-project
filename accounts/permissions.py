from rest_framework.permissions import BasePermission

from .models import CandidateProfile, Organization, OrganizationMembership, User


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


def user_can_view_candidate_resume(user, resume, application=None):
    if not user.is_authenticated:
        return False
    if resume.candidate.user_id == user.pk:
        return True
    if user.role != User.Role.EMPLOYER:
        return False
    if resume.resume_visibility == CandidateProfile.ResumeVisibility.PUBLIC:
        return True
    if resume.resume_visibility == CandidateProfile.ResumeVisibility.AFTER_APPLICATION:
        applications = resume.candidate.applications
        return applications.filter(vacancy__organization__memberships__user=user).exists() or (
            applications.filter(vacancy__organization__owner=user).exists()
        )
    if resume.resume_visibility != CandidateProfile.ResumeVisibility.PRIVATE or application is None:
        return False
    return (
        application.resume_id == resume.pk
        and application.candidate_id == resume.candidate_id
        and has_organization_access(user, application.vacancy.organization)
    )
