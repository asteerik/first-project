from rest_framework import serializers
from django.urls import reverse

from accounts.models import CandidateResume, Organization, User
from accounts.permissions import has_organization_access, user_can_view_resume
from accounts.serializers import PublicCandidateSerializer, PublicOrganizationSerializer
from .models import Application, Category, Complaint, Favorite, Vacancy


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")
        read_only_fields = fields


class VacancySerializer(serializers.ModelSerializer):
    organization = PublicOrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        queryset=Organization.objects.all(),
        write_only=True,
    )
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.filter(is_active=True),
        write_only=True,
    )
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Vacancy
        fields = (
            "id",
            "organization",
            "organization_id",
            "category",
            "category_id",
            "created_by",
            "title",
            "description",
            "requirements",
            "location",
            "employment_type",
            "salary_min",
            "salary_max",
            "status",
            "moderation_note",
            "published_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "status",
            "moderation_note",
            "published_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        minimum = attrs.get("salary_min", getattr(self.instance, "salary_min", None))
        maximum = attrs.get("salary_max", getattr(self.instance, "salary_max", None))
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError({"salary_max": "Зарплата «до» не может быть меньше зарплаты «от»."})
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get("request")
        user = request.user if request else None
        is_moderator = bool(
            user
            and user.is_authenticated
            and user.role in (User.Role.MODERATOR, User.Role.ADMIN)
        )
        can_manage = bool(user and has_organization_access(user, instance.organization))
        if not (is_moderator or can_manage):
            representation.pop("created_by", None)
            representation["moderation_note"] = ""
        return representation


class ApplicationSerializer(serializers.ModelSerializer):
    candidate = serializers.SerializerMethodField()
    selected_resume = serializers.SerializerMethodField()
    vacancy_title = serializers.CharField(source="vacancy.title", read_only=True)
    resume_id = serializers.PrimaryKeyRelatedField(
        source="resume",
        queryset=CandidateResume.objects.none(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    vacancy_id = serializers.PrimaryKeyRelatedField(
        source="vacancy",
        queryset=Vacancy.objects.filter(
            status=Vacancy.Status.APPROVED,
            organization__verification_status="approved",
        ),
        write_only=True,
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "vacancy",
            "vacancy_id",
            "vacancy_title",
            "candidate",
            "resume_id",
            "selected_resume",
            "cover_letter",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "vacancy", "vacancy_title", "candidate", "status", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
            self.fields["resume_id"].queryset = CandidateResume.objects.filter(
                candidate__user=request.user
            )

    def get_candidate(self, application):
        request = self.context.get("request")
        if request and user_can_view_resume(request.user, application.candidate):
            return PublicCandidateSerializer(application.candidate).data
        return {"id": application.candidate_id, "full_name": application.candidate.full_name}

    def get_selected_resume(self, application):
        resume = application.resume
        if not resume:
            return None
        details = {
            "id": resume.pk,
            "title": resume.title,
            "desired_position": resume.desired_position,
            "experience": resume.experience,
            "education": resume.education,
            "portfolio_url": resume.portfolio_url,
            "resume_file_name": resume.resume_file_name,
        }
        if resume.resume_file:
            details["download_url"] = reverse(
                "jobs:application_resume",
                kwargs={"pk": application.pk},
            )
        return details

    def validate(self, attrs):
        if self.instance is None:
            return attrs
        allowed = {"cover_letter"}
        if set(self.initial_data) - allowed:
            raise serializers.ValidationError("Можно изменить только сопроводительное письмо.")
        return attrs


class ApplicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ("status",)


class FavoriteSerializer(serializers.ModelSerializer):
    vacancy = VacancySerializer(read_only=True)
    vacancy_id = serializers.PrimaryKeyRelatedField(
        source="vacancy",
        queryset=Vacancy.objects.filter(
            status=Vacancy.Status.APPROVED,
            organization__verification_status="approved",
        ),
        write_only=True,
    )

    class Meta:
        model = Favorite
        fields = ("id", "vacancy", "vacancy_id", "created_at")
        read_only_fields = ("id", "vacancy", "created_at")


class ComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = ("id", "vacancy", "organization", "reason", "details", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")

    def validate(self, attrs):
        if self.instance is None:
            vacancy = attrs.get("vacancy")
            organization = attrs.get("organization")
            if (vacancy is None) == (organization is None):
                raise serializers.ValidationError("Укажите либо вакансию, либо организацию.")
        return attrs
