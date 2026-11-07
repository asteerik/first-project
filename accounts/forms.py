import re
from pathlib import Path

from django import forms
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import transaction

from .models import CandidateProfile, CandidateResume
from .rich_text import sanitize_rich_text
from .serializers import RegistrationSerializer

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 60
PERSON_NAME_PATTERN = re.compile(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*", re.UNICODE)
POPULAR_POSITIONS = (
    "Бухгалтер",
    "Воспитатель",
    "Делопроизводитель",
    "Медицинская сестра",
    "Педагог",
    "Повар",
    "Регент",
    "Социальный работник",
)


def person_name_field(label, required=True):
    return forms.CharField(
        label=label,
        required=required,
        max_length=80,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


def resume_form_fields(form):
    for name in ("surname", "first_name"):
        form.fields[name].required = True
    for name in ("surname", "first_name", "patronymic"):
        form.fields[name].widget.attrs["autocomplete"] = {
            "surname": "family-name",
            "first_name": "given-name",
            "patronymic": "additional-name",
        }[name]
    form.fields["phone"].required = True
    form.fields["phone"].help_text = "Укажите номер из 10 цифр; код +7 добавится автоматически."
    form.fields["location"].widget.attrs.update(
        {"list": "region-suggestions", "autocomplete": "address-level2"}
    )
    form.fields["desired_position"].widget.attrs["list"] = "position-suggestions"
    form.fields["desired_position"].widget.attrs["data-custom-autocomplete"] = "true"
    form.fields["location"].widget.attrs["data-custom-autocomplete"] = "true"
    form.fields["resume_visibility"].widget.attrs["class"] = "js-custom-select"
    if "title" in form.fields:
        form.fields["title"].label = "Название резюме *"
    form.fields["portfolio_url"].help_text = "GitHub, LinkedIn, Behance или ваш личный сайт."
    form.fields["experience"].widget.attrs.update({"rows": 5, "data-rich-text": "true"})
    form.fields["education"].widget.attrs.update({"rows": 4, "data-rich-text": "true"})
    form.fields["resume_visibility"].help_text = (
        "Только мне — никто другой не увидит. После отклика — работодатели по вашим откликам. "
        "Публичное — работодатели могут посмотреть данные и прикреплённый файл резюме."
    )
    form.fields["resume_file"].help_text = "PDF или DOCX, размером до 5 МБ."
    form.fields["resume_file"].widget.attrs.update(
        {"accept": ".pdf,.docx", "data-file-input": "true"}
    )
    form.fields["experience"].label = "Опыт и навыки"
    form.fields["education"].label = "Образование"
    form.fields["experience"].help_text = "Совет: добавьте не менее 100 символов, чтобы рассказать о себе подробнее."
    form.fields["education"].help_text = "Совет: добавьте не менее 100 символов, если есть что рассказать."


def validate_person_name(value):
    if not value.strip():
        return ""
    if not PERSON_NAME_PATTERN.fullmatch(value.strip()):
        raise forms.ValidationError("Используйте буквы, пробел, дефис или апостроф.")
    return value.strip()


def login_attempts_key(request):
    return f"web-login-attempts:{request.META.get('REMOTE_ADDR', '')}"


class WebLoginForm(forms.Form):
    email = forms.EmailField(label="Электронная почта")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        key = login_attempts_key(self.request)
        attempts = cache.get(key, 0)
        if attempts >= LOGIN_ATTEMPT_LIMIT:
            raise forms.ValidationError("Слишком много попыток входа. Повторите через минуту.")
        self.user = authenticate(self.request, username=cleaned["email"], password=cleaned["password"])
        if self.user is None:
            cache.set(key, attempts + 1, LOGIN_ATTEMPT_WINDOW)
            raise forms.ValidationError("Неверная почта или пароль.")
        return cleaned


class CandidateRegistrationForm(forms.Form):
    role = "candidate"
    full_name = forms.CharField(label="Имя и фамилия", max_length=200)
    email = forms.EmailField(label="Электронная почта")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput, strip=False)

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        serializer = RegistrationSerializer(data={**cleaned, "role": self.role})
        if not serializer.is_valid():
            for field, messages in serializer.errors.items():
                target = field if field in self.fields else None
                for message in messages:
                    self.add_error(target, str(message))
            return cleaned
        self.serializer = serializer
        return cleaned

    def save(self):
        return self.serializer.save()


class EmployerRegistrationForm(CandidateRegistrationForm):
    full_name = None
    organization_name = forms.CharField(label="Название организации", max_length=200)
    email = forms.EmailField(label="Электронная почта")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput, strip=False)
    field_order = ("organization_name", "email", "password")
    role = "employer"


class ResumeForm(forms.ModelForm):
    surname = person_name_field("Фамилия *")
    first_name = person_name_field("Имя *")
    patronymic = person_name_field("Отчество", required=False)
    remove_resume_file = forms.BooleanField(label="Удалить прикреплённый файл", required=False)

    class Meta:
        model = CandidateProfile
        fields = (
            "surname",
            "first_name",
            "patronymic",
            "phone",
            "location",
            "desired_position",
            "portfolio_url",
            "experience",
            "education",
            "resume_visibility",
            "resume_file",
        )
        widgets = {
            "phone": forms.TextInput(
                attrs={
                    "type": "tel",
                    "inputmode": "tel",
                    "pattern": r"\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}",
                    "maxlength": 32,
                    "placeholder": "+7 (900) 000-00-00",
                    "autocomplete": "tel",
                    "data-phone-mask": "ru",
                }
            ),
            "location": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "desired_position": forms.TextInput(attrs={"autocomplete": "organization-title"}),
            "portfolio_url": forms.URLInput(attrs={"placeholder": "https://example.com"}),
            "experience": forms.Textarea(attrs={"rows": 5}),
            "education": forms.Textarea(attrs={"rows": 4}),
            "resume_file": forms.FileInput(attrs={"accept": ".pdf,.docx", "data-file-input": "true"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_file_name = self.instance.resume_file.name if self.instance.resume_file else ""
        if self.instance.pk:
            for name in ("surname", "first_name", "patronymic"):
                self.initial.setdefault(name, getattr(self.instance, name))
        resume_form_fields(self)
        if not self.old_file_name:
            self.fields.pop("remove_resume_file")

    def clean_surname(self):
        return validate_person_name(self.cleaned_data["surname"])

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data["first_name"])

    def clean_patronymic(self):
        return validate_person_name(self.cleaned_data["patronymic"])

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if not re.fullmatch(r"[0-9+() .-]+", phone):
            raise forms.ValidationError("Используйте только цифры и символы + ( ) . -.")
        digits = re.sub(r"\D", "", phone)
        if len(digits) != 11 or not digits.startswith("7"):
            raise forms.ValidationError("Введите российский номер в формате +7 (900) 000-00-00.")
        return phone

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("remove_resume_file") and self.files.get("resume_file"):
            self.add_error("resume_file", "Выберите: заменить файл или удалить его.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        for name in ("surname", "first_name", "patronymic"):
            setattr(profile, name, self.cleaned_data[name])
        profile.full_name = " ".join(
            part for part in (profile.first_name, profile.surname, profile.patronymic) if part
        )
        for name in ("experience", "education"):
            setattr(profile, name, sanitize_rich_text(self.cleaned_data[name]))
        if "resume_file" in self.changed_data:
            uploaded = self.files.get("resume_file")
            profile.resume_file_name = Path(uploaded.name).name[:255] if uploaded else ""
        if self.cleaned_data.get("remove_resume_file"):
            profile.resume_file = None
            profile.resume_file_name = ""
        if commit:
            with transaction.atomic():
                profile.save()
            if self.old_file_name and self.old_file_name != (profile.resume_file.name or ""):
                profile.resume_file.storage.delete(self.old_file_name)
        return profile


class CandidateResumeForm(forms.ModelForm):
    surname = person_name_field("Фамилия *")
    first_name = person_name_field("Имя *")
    patronymic = person_name_field("Отчество", required=False)
    phone = forms.CharField(
        label="Телефон *",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "type": "tel",
                "inputmode": "tel",
                "pattern": r"\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}",
                "maxlength": 32,
                "placeholder": "+7 (900) 000-00-00",
                "autocomplete": "tel",
                "data-phone-mask": "ru",
            }
        ),
    )
    location = forms.CharField(label="Город или регион", max_length=120, required=False)
    latitude = forms.DecimalField(
        label="Широта",
        required=False,
        min_value=-90,
        max_value=90,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "latitude"}),
    )
    longitude = forms.DecimalField(
        label="Долгота",
        required=False,
        min_value=-180,
        max_value=180,
        max_digits=9,
        decimal_places=6,
        widget=forms.HiddenInput(attrs={"id": "longitude"}),
    )
    preferred_radius_km = forms.IntegerField(
        label="Желаемый радиус поиска, км",
        required=False,
        min_value=1,
        max_value=200,
        widget=forms.HiddenInput(attrs={"id": "radius-input"}),
    )
    remove_resume_file = forms.BooleanField(label="Удалить прикреплённый файл", required=False)

    class Meta:
        model = CandidateResume
        fields = (
            "title",
            "desired_position",
            "portfolio_url",
            "experience",
            "education",
            "latitude",
            "longitude",
            "preferred_radius_km",
            "resume_visibility",
            "resume_file",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Например, Регент приходского хора"}),
            "desired_position": forms.TextInput(attrs={"list": "position-suggestions"}),
            "portfolio_url": forms.URLInput(attrs={"placeholder": "https://example.com"}),
            "experience": forms.Textarea(attrs={"rows": 6}),
            "education": forms.Textarea(attrs={"rows": 3}),
            "resume_file": forms.FileInput(attrs={"accept": ".pdf,.docx", "data-file-input": "true"}),
        }

    def __init__(self, *args, **kwargs):
        self.candidate_profile = kwargs.pop("candidate_profile", None)
        super().__init__(*args, **kwargs)
        self.old_file_name = self.instance.resume_file.name if self.instance.resume_file else ""
        if self.candidate_profile:
            for name in ("surname", "first_name", "patronymic", "phone", "location"):
                self.initial.setdefault(name, getattr(self.candidate_profile, name))
        self.field_order = [
            "surname",
            "first_name",
            "patronymic",
            "phone",
            "location",
            "latitude",
            "longitude",
            "preferred_radius_km",
            "title",
            "desired_position",
            "portfolio_url",
            "experience",
            "education",
            "resume_visibility",
            "resume_file",
        ]
        resume_form_fields(self)
        if not self.old_file_name:
            self.fields.pop("remove_resume_file")

    def clean_surname(self):
        return validate_person_name(self.cleaned_data["surname"])

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data["first_name"])

    def clean_patronymic(self):
        return validate_person_name(self.cleaned_data["patronymic"])

    def clean_preferred_radius_km(self):
        return self.cleaned_data["preferred_radius_km"] or 50

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if not re.fullmatch(r"[0-9+() .-]+", phone):
            raise forms.ValidationError("Используйте только цифры и символы + ( ) . -.")
        digits = re.sub(r"\D", "", phone)
        if len(digits) != 11 or not digits.startswith("7"):
            raise forms.ValidationError("Введите российский номер в формате +7 (900) 000-00-00.")
        return phone

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("latitude") is None) != (cleaned.get("longitude") is None):
            self.add_error(None, "Выберите точку на карте или очистите обе координаты.")
        if cleaned.get("remove_resume_file") and self.files.get("resume_file"):
            self.add_error("resume_file", "Выберите: заменить файл или удалить его.")
        return cleaned

    def save(self, commit=True):
        resume = super().save(commit=False)
        profile = self.candidate_profile or self.instance.candidate
        for name in ("surname", "first_name", "patronymic", "phone", "location"):
            setattr(profile, name, self.cleaned_data[name])
        profile.full_name = " ".join(
            part for part in (profile.first_name, profile.surname, profile.patronymic) if part
        )
        self.instance.candidate = profile
        for name in ("experience", "education"):
            setattr(resume, name, sanitize_rich_text(self.cleaned_data[name]))
        if "resume_file" in self.changed_data:
            uploaded = self.files.get("resume_file")
            resume.resume_file_name = Path(uploaded.name).name[:255] if uploaded else ""
        if self.cleaned_data.get("remove_resume_file"):
            resume.resume_file = None
            resume.resume_file_name = ""
        if commit:
            with transaction.atomic():
                profile.save()
                resume.save()
            if self.old_file_name and self.old_file_name != (resume.resume_file.name or ""):
                resume.resume_file.storage.delete(self.old_file_name)
        return resume
