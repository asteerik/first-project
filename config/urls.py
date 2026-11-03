from django.contrib import admin
from django.urls import include, path

from .page_views import HomeView, PlaceholderView

# Временные страницы: имена нужны шаблону главной; участник 2 заменит их настоящими.
jobs_pages = [
    path("vacancies/", PlaceholderView.as_view(title="Вакансии"), name="list"),
    path("vacancies/<int:pk>/", PlaceholderView.as_view(title="Вакансия"), name="detail"),
]
accounts_pages = [
    path("login/", PlaceholderView.as_view(title="Вход"), name="login"),
    path("register/", PlaceholderView.as_view(title="Регистрация"), name="register_as_seeker"),
]
info_pages = [
    path("about/", PlaceholderView.as_view(title="О проекте"), name="about"),
    path("help/", PlaceholderView.as_view(title="Помощь"), name="help"),
    path("contacts/", PlaceholderView.as_view(title="Контакты"), name="contacts"),
]

urlpatterns = [
    path("", HomeView.as_view(), name="homepage"),
    path("", include((jobs_pages, "jobs"))),
    path("", include((accounts_pages, "accounts"))),
    path("", include((info_pages, "pages"))),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("jobs.urls")),
]
