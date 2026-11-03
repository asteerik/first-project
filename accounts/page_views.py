from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, UpdateView

from .forms import CandidateRegistrationForm, EmployerRegistrationForm, ResumeForm, WebLoginForm
from .models import CandidateProfile, User


def safe_next_url(request, default):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return default


class LoginPage(FormView):
    template_name = "accounts/login.html"
    form_class = WebLoginForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
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

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, "Регистрация прошла успешно. Заполните резюме.")
        return redirect("accounts:resume")


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
        response = super().form_valid(form)
        messages.success(self.request, "Резюме сохранено.")
        return response
