from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from rest_framework.exceptions import ValidationError

from .models import Category, Vacancy
from .views import apply_region_filter

PAGE_SIZE = 9
REGIONS = [
    ("moscow", "Москва"),
    ("spb", "Санкт-Петербург"),
    ("nk", "Нижегородская область"),
    ("other", "Другие регионы"),
]


def published_vacancies():
    return Vacancy.objects.filter(status=Vacancy.Status.APPROVED).select_related("organization", "category")


class VacancyListPage(TemplateView):
    template_name = "jobs/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        query = params.get("q", "").strip()
        region = params.get("region", "").strip()
        category = params.get("category", "").strip()

        queryset = published_vacancies()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(organization__name__icontains=query)
            )
        if region:
            try:
                queryset = apply_region_filter(queryset, region)
            except ValidationError:
                region = ""
        if category:
            queryset = queryset.filter(category__slug=category)

        page = Paginator(queryset, PAGE_SIZE).get_page(params.get("page"))
        extra_params = params.copy()
        extra_params.pop("page", None)
        context.update(
            nav_current="jobs",
            page=page,
            query=query,
            region=region,
            category=category,
            regions=REGIONS,
            categories=Category.objects.filter(is_active=True),
            filter_query=extra_params.urlencode(),
        )
        return context


class VacancyDetailPage(TemplateView):
    template_name = "jobs/detail.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        vacancy = get_object_or_404(published_vacancies(), pk=pk)
        context.update(nav_current="jobs", vacancy=vacancy)
        return context
