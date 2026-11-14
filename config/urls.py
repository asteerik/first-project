from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .page_views import AboutPage, HomeView, PlaceholderView
from jobs.page_views import (
    ApplicationResumeDownloadPage,
    CandidateApplicationResponsePage,
    CandidateApplicationsPage,
    VacancyApplicationPage,
    VacancyDetailPage,
    VacancyListPage,
)
from jobs.employer_views import (
    EmployerApplicationStatusPage,
    EmployerDashboard,
    EmployerResumeCatalog,
    EmployerResumeDownloadPage,
    VacancyClosePage,
    VacancyCreatePage,
    VacancyEditPage,
)
from accounts.page_views import (
    EmployerRegisterPage,
    LoginPage,
    LogoutPage,
    RegisterPage,
    ResumeCreatePage,
    ResumeDeletePage,
    ResumeDownloadPage,
    ResumeEditPage,
    ResumeListPage,
    ResumePage,
)

# Временные страницы: имена нужны шаблону главной; участник 2 заменит их настоящими.
jobs_pages = [
    path("vacancies/", VacancyListPage.as_view(), name="list"),
    path("vacancies/<int:pk>/", VacancyDetailPage.as_view(), name="detail"),
    path("vacancies/<int:pk>/apply/", VacancyApplicationPage.as_view(), name="apply"),
    path("my-applications/", CandidateApplicationsPage.as_view(), name="candidate_applications"),
    path(
        "my-applications/<int:pk>/response/",
        CandidateApplicationResponsePage.as_view(),
        name="candidate_application_response",
    ),
    path(
        "applications/<int:pk>/resume/",
        ApplicationResumeDownloadPage.as_view(),
        name="application_resume",
    ),
    path("employer/", EmployerDashboard.as_view(), name="employer_dashboard"),
    path("employer/resumes/", EmployerResumeCatalog.as_view(), name="employer_resume_catalog"),
    path(
        "employer/resumes/<int:pk>/download/",
        EmployerResumeDownloadPage.as_view(),
        name="employer_resume_download",
    ),
    path(
        "employer/applications/<int:pk>/status/",
        EmployerApplicationStatusPage.as_view(),
        name="employer_application_status",
    ),
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
    path("resumes/", ResumeListPage.as_view(), name="resumes"),
    path("resumes/new/", ResumeCreatePage.as_view(), name="resume_create"),
    path("resumes/<int:pk>/edit/", ResumeEditPage.as_view(), name="resume_edit"),
    path("resumes/<int:pk>/delete/", ResumeDeletePage.as_view(), name="resume_delete"),
    path(
        "resumes/<int:pk>/download/",
        ResumeDownloadPage.as_view(),
        name="resume_download",
    ),
]
info_pages = [
    path("about/", AboutPage.as_view(), name="about"),
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
