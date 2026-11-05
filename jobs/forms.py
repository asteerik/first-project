from django import forms

from accounts.models import CandidateResume

from .models import Application


class ApplicationForm(forms.ModelForm):
    resume = forms.ModelChoiceField(
        label="Резюме для работодателя",
        queryset=CandidateResume.objects.none(),
        widget=forms.Select(attrs={"class": "js-custom-select"}),
    )

    class Meta:
        model = Application
        fields = ("resume", "cover_letter")
        widgets = {
            "cover_letter": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Коротко расскажите, почему вам интересна эта работа.",
                }
            ),
        }

    def __init__(self, *args, candidate_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if candidate_profile:
            self.fields["resume"].queryset = CandidateResume.objects.filter(
                candidate=candidate_profile
            )
