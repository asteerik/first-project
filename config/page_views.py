from django.views.generic import TemplateView

from jobs.models import Vacancy


class HomeView(TemplateView):
    template_name = "pages/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vacancies"] = Vacancy.objects.filter(status=Vacancy.Status.APPROVED).select_related(
            "organization", "category"
        )[:6]
        return context


class PlaceholderView(TemplateView):
    """Временная страница, пока участник 2 не добавит настоящую."""

    template_name = "pages/placeholder.html"
    title = "Страница в разработке"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context
