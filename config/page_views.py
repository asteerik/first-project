from django.views.generic import TemplateView

from accounts.models import Organization
from jobs.models import Category, Vacancy
from jobs.regions import REGION_SUGGESTIONS


class HomeView(TemplateView):
    template_name = "pages/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vacancies"] = Vacancy.objects.filter(status=Vacancy.Status.APPROVED).select_related(
            "organization", "category"
        )[:6]
        context["region_suggestions"] = REGION_SUGGESTIONS
        context["categories"] = Category.objects.filter(is_active=True)
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
