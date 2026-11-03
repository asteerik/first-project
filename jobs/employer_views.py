from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from accounts.models import Organization, User

from .models import Category, Vacancy


def employer_organizations(user):
    return Organization.objects.filter(Q(owner=user) | Q(memberships__user=user)).distinct()


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = (
            "category",
            "title",
            "location",
            "employment_type",
            "salary_min",
            "salary_max",
            "description",
            "requirements",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 7}),
            "requirements": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, organizations, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["category"].empty_label = "Выберите категорию"
        self.organizations = list(organizations)
        if len(self.organizations) > 1:
            self.fields["organization"] = forms.ModelChoiceField(
                label="Организация",
                queryset=Organization.objects.filter(pk__in=[o.pk for o in self.organizations]),
                initial=self.instance.organization_id or None,
            )
            self.order_fields(("organization",))

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 50:
            raise forms.ValidationError("Опишите вакансию подробнее: не меньше 50 символов.")
        return description

    def clean(self):
        cleaned = super().clean()
        minimum, maximum = cleaned.get("salary_min"), cleaned.get("salary_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("salary_max", "Зарплата «до» не может быть меньше зарплаты «от».")
        return cleaned

    def save(self, commit=True):
        vacancy = super().save(commit=False)
        vacancy.organization = self.cleaned_data.get("organization") or self.organizations[0]
        vacancy.status = Vacancy.Status.PENDING
        vacancy.moderation_note = ""
        vacancy.published_at = None
        if commit:
            vacancy.save()
        return vacancy


class EmployerRequiredMixin(LoginRequiredMixin):
    login_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            if user.role != User.Role.EMPLOYER:
                messages.error(request, "Эта страница доступна только работодателям.")
                return redirect("homepage")
            self.organizations = employer_organizations(user)
            if not self.organizations.exists():
                messages.error(request, "У вашего аккаунта нет организации.")
                return redirect("homepage")
        return super().dispatch(request, *args, **kwargs)


class EmployerDashboard(EmployerRequiredMixin, ListView):
    template_name = "jobs/employer/dashboard.html"
    context_object_name = "vacancies"

    def get_queryset(self):
        return (
            Vacancy.objects.filter(organization__in=self.organizations)
            .select_related("organization", "category")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organizations"] = self.organizations
        return context


class VacancyFormMixin(EmployerRequiredMixin):
    form_class = VacancyForm
    template_name = "jobs/employer/vacancy_form.html"
    success_url = reverse_lazy("jobs:employer_dashboard")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "organizations": self.organizations}

    def form_valid(self, form):
        vacancy = form.save(commit=False)
        if not vacancy.pk:
            vacancy.created_by = self.request.user
        vacancy.save()
        messages.success(self.request, "Вакансия отправлена на проверку модератору.")
        return redirect(self.success_url)


class VacancyCreatePage(VacancyFormMixin, CreateView):
    pass


class VacancyEditPage(VacancyFormMixin, UpdateView):
    def get_queryset(self):
        return Vacancy.objects.filter(organization__in=self.organizations).exclude(status=Vacancy.Status.CLOSED)


class VacancyClosePage(EmployerRequiredMixin, View):
    def post(self, request, pk):
        vacancy = get_object_or_404(Vacancy, pk=pk, organization__in=self.organizations)
        vacancy.status = Vacancy.Status.CLOSED
        vacancy.published_at = None
        vacancy.save(update_fields=["status", "published_at", "updated_at"])
        messages.success(request, "Вакансия закрыта.")
        return redirect("jobs:employer_dashboard")
