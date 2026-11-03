from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .page_views import HomeView, PlaceholderView
from jobs.page_views import VacancyDetailPage, VacancyListPage
from jobs.employer_views import (
    EmployerDashboard,
    VacancyClosePage,
    VacancyCreatePage,
    VacancyEditPage,
)
from accounts.page_views import EmployerRegisterPage, LoginPage, LogoutPage, RegisterPage, ResumePage

# Временные страницы: имена нужны шаблону главной; участник 2 заменит их настоящими.
jobs_pages = [
    path("vacancies/", VacancyListPage.as_view(), name="list"),
    path("vacancies/<int:pk>/", VacancyDetailPage.as_view(), name="detail"),
    path("employer/", EmployerDashboard.as_view(), name="employer_dashboard"),
    path("employer/vacancies/new/", VacancyCreatePage.as_view(), name="employer_vacancy_new"),
    path("employer/vacancies/<int:pk>/edit/", VacancyEditPage.as_view(), name="employer_vacancy_edit"),
    path("employer/vacancies/<int:pk>/close/", VacancyClosePage.as_view(), name="employer_vacancy_close"),
]
accounts_pages = [
    path("login/", LoginPage.as_view(), name="login"),
    path("register/", RegisterPage.as_view(), name="register_as_seeker"),
    path("register/employer/", EmployerRegisterPage.as_view(), name="register_as_employer"),
    path("logout/", LogoutPage.as_view(), name="logout"),
    path("resume/", ResumePage.as_view(), name="resume"),
]
info_pages = [
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
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
