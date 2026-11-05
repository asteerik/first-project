from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView, TemplateView
from rest_framework.exceptions import ValidationError

from accounts.models import CandidateProfile, CandidateResume, Organization, User
from accounts.permissions import has_organization_access

from .forms import ApplicationForm
from .models import Application, Category, Vacancy
from .regions import REGION_SUGGESTIONS
from .views import apply_region_filter

PAGE_SIZE = 9


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
            region_suggestions=REGION_SUGGESTIONS,
            categories=Category.objects.filter(is_active=True),
            filter_query=extra_params.urlencode(),
        )
        return context


class VacancyDetailPage(TemplateView):
    template_name = "jobs/detail.html"

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        vacancy = get_object_or_404(published_vacancies(), pk=pk)
        has_applied = False
        resumes = CandidateResume.objects.none()
        application_form = None
        if self.request.user.is_authenticated and self.request.user.role == User.Role.CANDIDATE:
            has_applied = vacancy.applications.filter(candidate__user=self.request.user).exists()
            try:
                candidate = self.request.user.candidate_profile
            except CandidateProfile.DoesNotExist:
                candidate = None
            if candidate:
                resumes = CandidateResume.objects.filter(candidate=candidate)
                application_form = ApplicationForm(candidate_profile=candidate)
        resume_return_url = f"{reverse('jobs:detail', kwargs={'pk': vacancy.pk})}?apply=1"
        context.update(
            nav_current="jobs",
            vacancy=vacancy,
            requirement_lines=[
                line.strip() for line in vacancy.requirements.splitlines() if line.strip()
            ],
            has_applied=has_applied,
            resumes=resumes,
            application_form=application_form,
            has_resumes=resumes.exists(),
            open_application_dialog=self.request.GET.get("apply") == "1",
            resume_return_url=resume_return_url,
        )
        return context


class VacancyApplicationPage(LoginRequiredMixin, FormView):
    template_name = "jobs/apply.html"
    form_class = ApplicationForm
    login_url = "accounts:login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Откликнуться на вакансию могут только соискатели.")
            return redirect("jobs:detail", pk=kwargs["pk"])
        self.vacancy = get_object_or_404(
            published_vacancies().filter(
                organization__verification_status="approved",
            ),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse('jobs:detail', kwargs={'pk': self.vacancy.pk})}?apply=1")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate, _ = CandidateProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"full_name": self.request.user.email},
        )
        context.update(
            nav_current="jobs",
            vacancy=self.vacancy,
            has_resumes=CandidateResume.objects.filter(candidate=candidate).exists(),
            resume_return_url=(
                f"{reverse('jobs:detail', kwargs={'pk': self.vacancy.pk})}?apply=1"
            ),
        )
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        candidate, _ = CandidateProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"full_name": self.request.user.email},
        )
        kwargs["candidate_profile"] = candidate
        return kwargs

    def form_valid(self, form):
        candidate = self.request.user.candidate_profile
        _, created = Application.objects.get_or_create(
            vacancy=self.vacancy,
            candidate=candidate,
            defaults={
                "resume": form.cleaned_data["resume"],
                "cover_letter": form.cleaned_data["cover_letter"],
            },
        )
        if created:
            messages.success(self.request, "Ваш отклик отправлен работодателю.")
        else:
            messages.info(self.request, "Вы уже откликались на эту вакансию.")
        return redirect(reverse("jobs:detail", kwargs={"pk": self.vacancy.pk}))


class ApplicationResumeDownloadPage(LoginRequiredMixin, View):
    login_url = "accounts:login"

    def get(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related(
                "candidate",
                "vacancy__organization",
                "resume",
            ),
            pk=pk,
        )
        is_candidate = (
            request.user.role == User.Role.CANDIDATE
            and application.candidate.user_id == request.user.pk
        )
        is_employer = (
            request.user.role == User.Role.EMPLOYER
            and has_organization_access(request.user, application.vacancy.organization)
        )
        if not (is_candidate or is_employer):
            raise Http404
        if not application.resume or not application.resume.resume_file:
            raise Http404
        return FileResponse(
            application.resume.resume_file.open("rb"),
            as_attachment=True,
            filename=application.resume.resume_file_name or "resume",
        )


class CandidateApplicationsPage(LoginRequiredMixin, ListView):
    template_name = "jobs/candidate_applications.html"
    context_object_name = "applications"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Эта страница доступна только соискателям.")
            return redirect("homepage")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Application.objects.filter(candidate__user=self.request.user)
            .select_related("vacancy", "vacancy__organization", "resume")
            .order_by("-created_at")
        )


class CandidateApplicationResponsePage(LoginRequiredMixin, View):
    login_url = "accounts:login"

    def post(self, request, pk):
        if request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Ответить на приглашение может только соискатель.")
            return redirect("homepage")
        application = get_object_or_404(
            Application.objects.select_related("candidate__user"),
            pk=pk,
            candidate__user=request.user,
            status=Application.Status.INVITED,
        )
        new_status = request.POST.get("status")
        if new_status not in (Application.Status.ACCEPTED, Application.Status.REJECTED):
            messages.error(request, "Выберите, принять или отклонить приглашение.")
            return redirect("jobs:candidate_applications")
        application.status = new_status
        application.save(update_fields=["status", "updated_at"])
        messages.success(request, "Ваш ответ отправлен работодателю.")
        return redirect("jobs:candidate_applications")
