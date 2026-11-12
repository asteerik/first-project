from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, FormView, TemplateView, UpdateView

from .forms import (
    POPULAR_POSITIONS,
    CandidateRegistrationForm,
    CandidateResumeForm,
    EmployerRegistrationForm,
    ResumeForm,
    WebLoginForm,
)
from .models import CandidateProfile, CandidateResume, User
from jobs.regions import REGION_SUGGESTIONS


def safe_next_url(request, default):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return default


def save_resume_as_draft(request, form):
    if not request.POST.get("save_as_draft"):
        return False
    form.cleaned_data["resume_visibility"] = CandidateProfile.ResumeVisibility.PRIVATE
    form.instance.resume_visibility = CandidateProfile.ResumeVisibility.PRIVATE
    return True


class LoginPage(FormView):
    template_name = "accounts/login.html"
    form_class = WebLoginForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.POST.get("next") or self.request.GET.get("next", "")
        return context

    def form_valid(self, form):
        login(self.request, form.user)
        if form.user.role == User.Role.CANDIDATE:
            default = reverse("accounts:resume")
        elif form.user.role == User.Role.EMPLOYER:
            default = reverse("jobs:employer_dashboard")
        else:
            default = reverse("homepage")
        return redirect(safe_next_url(self.request, default))


class RegisterPage(FormView):
    template_name = "accounts/register.html"
    form_class = CandidateRegistrationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.POST.get("next") or self.request.GET.get("next", "")
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, "Регистрация прошла успешно. Заполните резюме.")
        return redirect(safe_next_url(self.request, reverse("accounts:resume")))


class EmployerRegisterPage(FormView):
    template_name = "accounts/register_employer.html"
    form_class = EmployerRegistrationForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            self.request,
            "Регистрация прошла успешно. Организация проверяется администратором, "
            "а вакансии появятся на сайте после проверки.",
        )
        return redirect("jobs:employer_dashboard")


class LogoutPage(View):
    def post(self, request):
        logout(request)
        return redirect("homepage")


class ResumePage(LoginRequiredMixin, UpdateView):
    template_name = "accounts/resume.html"
    form_class = ResumeForm
    success_url = reverse_lazy("homepage")
    login_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Резюме создают соискатели. Войдите под аккаунтом соискателя.")
            return redirect("homepage")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        profile, _ = CandidateProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"full_name": self.request.user.email},
        )
        return profile

    def form_valid(self, form):
        is_draft = save_resume_as_draft(self.request, form)
        response = super().form_valid(form)
        if is_draft:
            messages.success(self.request, "Черновик сохранён и доступен только вам.")
        else:
            messages.success(self.request, "Резюме сохранено.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["region_suggestions"] = REGION_SUGGESTIONS
        context["popular_positions"] = POPULAR_POSITIONS
        return context


class CandidatePageMixin(LoginRequiredMixin):
    login_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Раздел резюме доступен только соискателям.")
            return redirect("homepage")
        return super().dispatch(request, *args, **kwargs)

    def get_candidate_profile(self):
        profile, _ = CandidateProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"full_name": self.request.user.email},
        )
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["region_suggestions"] = REGION_SUGGESTIONS
        context["popular_positions"] = POPULAR_POSITIONS
        return context


class CandidateResumeFormPageMixin(CandidatePageMixin):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["candidate_profile"] = self.get_candidate_profile()
        return kwargs


class ResumeListPage(CandidatePageMixin, TemplateView):
    template_name = "accounts/resume_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resumes"] = CandidateResume.objects.filter(
            candidate__user=self.request.user
        )
        return context


class ResumeCreatePage(CandidateResumeFormPageMixin, CreateView):
    template_name = "accounts/resume_form.html"
    form_class = CandidateResumeForm
    success_url = reverse_lazy("accounts:resumes")

    def form_valid(self, form):
        form.instance.candidate = self.get_candidate_profile()
        is_draft = save_resume_as_draft(self.request, form)
        super().form_valid(form)
        if is_draft:
            messages.success(self.request, "Черновик сохранён и доступен только вам.")
        else:
            messages.success(self.request, "Резюме создано.")
        return redirect(safe_next_url(self.request, self.get_success_url()))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.POST.get("next") or self.request.GET.get("next", "")
        return context


class ResumeEditPage(CandidateResumeFormPageMixin, UpdateView):
    template_name = "accounts/resume_form.html"
    form_class = CandidateResumeForm
    success_url = reverse_lazy("accounts:resumes")

    def get_queryset(self):
        return CandidateResume.objects.filter(candidate__user=self.request.user)

    def form_valid(self, form):
        is_draft = save_resume_as_draft(self.request, form)
        response = super().form_valid(form)
        if is_draft:
            messages.success(self.request, "Черновик сохранён и доступен только вам.")
        else:
            messages.success(self.request, "Резюме обновлено.")
        return response


class ResumeDeletePage(CandidatePageMixin, View):
    def post(self, request, pk):
        resume = get_object_or_404(
            CandidateResume.objects.filter(candidate__user=request.user),
            pk=pk,
        )
        if resume.resume_file:
            resume.resume_file.delete(save=False)
        resume.delete()
        messages.success(request, "Резюме удалено.")
        return redirect("accounts:resumes")


class ResumeDownloadPage(CandidatePageMixin, View):
    def get(self, request, pk):
        resume = get_object_or_404(
            CandidateResume.objects.filter(candidate__user=request.user),
            pk=pk,
        )
        if not resume.resume_file:
            messages.error(request, "В этом резюме нет прикреплённого файла.")
            return redirect("accounts:resumes")
        return FileResponse(
            resume.resume_file.open("rb"),
            as_attachment=True,
            filename=resume.resume_file_name or "resume",
        )
