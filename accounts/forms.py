from pathlib import Path

from django import forms
from django.contrib.auth import authenticate
from django.core.cache import cache

from .models import CandidateProfile, CandidateResume
from .serializers import RegistrationSerializer

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 60


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
    class Meta:
        model = CandidateProfile
        fields = (
            "full_name",
            "phone",
            "location",
            "desired_position",
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
                    "pattern": r"[0-9+() .\-]*",
                    "maxlength": 32,
                    "placeholder": "+7 900 000-00-00",
                    "oninput": r"this.value=this.value.replace(/[^0-9+() .\-]/g,'')",
                }
            ),
            "experience": forms.Textarea(attrs={"rows": 6}),
            "education": forms.Textarea(attrs={"rows": 3}),
            "resume_file": forms.ClearableFileInput(attrs={"accept": ".pdf,.docx"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_file_name = self.instance.resume_file.name if self.instance.resume_file else ""

    def save(self, commit=True):
        profile = super().save(commit=False)
        if "resume_file" in self.changed_data:
            uploaded = self.files.get("resume_file")
            profile.resume_file_name = Path(uploaded.name).name[:255] if uploaded else ""
        if commit:
            profile.save()
            if self.old_file_name and self.old_file_name != (profile.resume_file.name or ""):
                profile.resume_file.storage.delete(self.old_file_name)
        return profile


class CandidateResumeForm(forms.ModelForm):
    class Meta:
        model = CandidateResume
        fields = (
            "title",
            "desired_position",
            "experience",
            "education",
            "resume_visibility",
            "resume_file",
        )
        widgets = {
            "experience": forms.Textarea(attrs={"rows": 6}),
            "education": forms.Textarea(attrs={"rows": 3}),
            "resume_file": forms.ClearableFileInput(attrs={"accept": ".pdf,.docx"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_file_name = self.instance.resume_file.name if self.instance.resume_file else ""

    def save(self, commit=True):
        resume = super().save(commit=False)
        if "resume_file" in self.changed_data:
            uploaded = self.files.get("resume_file")
            resume.resume_file_name = Path(uploaded.name).name[:255] if uploaded else ""
        if commit:
            resume.save()
            if self.old_file_name and self.old_file_name != (resume.resume_file.name or ""):
                resume.resume_file.storage.delete(self.old_file_name)
        return resume
