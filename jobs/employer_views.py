from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from accounts.models import Organization, User

from .models import Application, Category, Vacancy


class GroupedIntegerField(forms.IntegerField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
        return super().to_python(value)


def employer_organizations(user):
    return Organization.objects.filter(Q(owner=user) | Q(memberships__user=user)).distinct()


class VacancyForm(forms.ModelForm):
    salary_min = GroupedIntegerField(
        label="Зарплата от, руб.",
        required=False,
        min_value=0,
        max_value=100000000,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "data-grouped-number": "true"}
        ),
    )
    salary_max = GroupedIntegerField(
        label="Зарплата до, руб.",
        required=False,
        min_value=0,
        max_value=100000000,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "data-grouped-number": "true"}
        ),
    )
    latitude = forms.DecimalField(
        label="Широта точки вакансии",
        required=False,
        min_value=-90,
        max_value=90,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "latitude"}),
    )
    longitude = forms.DecimalField(
        label="Долгота точки вакансии",
        required=False,
        min_value=-180,
        max_value=180,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "longitude"}),
    )

    class Meta:
        model = Vacancy
        fields = (
            "category",
            "title",
            "location",
            "employment_type",
            "work_format",
            "latitude",
            "longitude",
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
        for field_name in ("category", "employment_type", "work_format"):
            self.fields[field_name].widget.attrs["class"] = "js-custom-select"
        self.organizations = list(organizations)
        if len(self.organizations) > 1:
            self.fields["organization"] = forms.ModelChoiceField(
                label="Организация",
                queryset=Organization.objects.filter(pk__in=[o.pk for o in self.organizations]),
                initial=self.instance.organization_id or None,
                widget=forms.Select(attrs={"class": "js-custom-select"}),
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
        if (cleaned.get("latitude") is None) != (cleaned.get("longitude") is None):
            self.add_error(None, "Выберите точку вакансии на карте или очистите обе координаты.")
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
        applications = (
            Application.objects.filter(vacancy__organization__in=self.organizations)
            .select_related("candidate", "vacancy", "resume")
            .order_by("-created_at")
        )
        application_tabs = (
            ("new", "Непросмотренные", Application.Status.NEW),
            ("reviewed", "Рассматриваются", Application.Status.REVIEWED),
            ("invited", "Ждут ответа", Application.Status.INVITED),
            ("rejected", "Отклонённые", Application.Status.REJECTED),
            ("accepted", "Принятые", Application.Status.ACCEPTED),
            ("withdrawn", "Отозванные", Application.Status.WITHDRAWN),
        )
        context["application_tabs"] = [
            {
                "key": key,
                "label": label,
                "count": applications.filter(status=status).count(),
            }
            for key, label, status in application_tabs
        ]
        selected_status = self.request.GET.get("applications", "new")
        status_by_key = {key: status for key, _, status in application_tabs}
        if selected_status not in status_by_key:
            selected_status = "new"
        context["selected_application_status"] = selected_status
        context["applications"] = applications.filter(status=status_by_key[selected_status])
        return context


class EmployerApplicationStatusPage(EmployerRequiredMixin, View):
    status_transitions = {
        Application.Status.NEW: {
            Application.Status.REVIEWED,
            Application.Status.INVITED,
            Application.Status.REJECTED,
        },
        Application.Status.REVIEWED: {
            Application.Status.INVITED,
            Application.Status.REJECTED,
        },
    }

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related("vacancy"),
            pk=pk,
            vacancy__organization__in=self.organizations,
        )
        new_status = request.POST.get("status")
        if new_status not in self.status_transitions.get(application.status, set()):
            messages.error(request, "Это действие недоступно для текущего статуса отклика.")
            return redirect("jobs:employer_dashboard")
        application.status = new_status
        application.save(update_fields=["status", "updated_at"])
        messages.success(request, "Статус отклика обновлён.")
        return redirect(f"{reverse('jobs:employer_dashboard')}?applications={new_status}")


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
