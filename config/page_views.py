from django.db.models import Q
from django.views.generic import TemplateView

from accounts.models import Organization, User
from jobs.models import Application, Category, Vacancy
from jobs.regions import REGION_SUGGESTIONS


class HomeView(TemplateView):
    template_name = "pages/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_employer"] = (
            self.request.user.is_authenticated
            and self.request.user.role == User.Role.EMPLOYER
        )
        context["vacancies"] = Vacancy.objects.filter(
            status=Vacancy.Status.APPROVED,
            organization__verification_status=Organization.VerificationStatus.APPROVED,
        ).select_related("organization", "category")[:6]
        context["region_suggestions"] = REGION_SUGGESTIONS
        context["categories"] = Category.objects.filter(is_active=True)
        if context["is_employer"]:
            organizations = Organization.objects.filter(
                Q(owner=self.request.user) | Q(memberships__user=self.request.user)
            ).distinct()
            employer_vacancies = Vacancy.objects.filter(
                organization__in=organizations
            ).select_related("organization", "category")
            context["employer_vacancies"] = employer_vacancies.order_by("-created_at")[:5]
            context["employer_vacancy_count"] = employer_vacancies.count()
            context["employer_pending_count"] = employer_vacancies.filter(
                status=Vacancy.Status.PENDING
            ).count()
            context["employer_published_count"] = employer_vacancies.filter(
                status=Vacancy.Status.APPROVED,
                organization__verification_status=Organization.VerificationStatus.APPROVED,
            ).count()
            context["employer_application_count"] = Application.objects.filter(
                vacancy__organization__in=organizations
            ).count()
            context["employer_has_organizations"] = organizations.exists()
        return context


class AboutPage(TemplateView):
    template_name = "pages/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["published_vacancy_count"] = Vacancy.objects.filter(
            status=Vacancy.Status.APPROVED,
            organization__verification_status=Organization.VerificationStatus.APPROVED,
        ).count()
        context["verified_organization_count"] = Organization.objects.filter(
            verification_status=Organization.VerificationStatus.APPROVED
        ).count()
        context["supported_resume_formats"] = 2
        return context


class PlaceholderView(TemplateView):
    """Временная страница, пока участник 2 не добавит настоящую."""

    template_name = "pages/placeholder.html"
    title = "Страница в разработке"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context
