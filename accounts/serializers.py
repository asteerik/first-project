from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import (
    CandidateProfile,
    Organization,
    OrganizationMembership,
    User,
)


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=[User.Role.CANDIDATE, User.Role.EMPLOYER])
    full_name = serializers.CharField(max_length=200, required=False)
    organization_name = serializers.CharField(max_length=200, required=False)

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с такой почтой уже зарегистрирован.")
        return value

    def validate(self, attrs):
        role = attrs["role"]
        if role == User.Role.CANDIDATE and not attrs.get("full_name", "").strip():
            raise serializers.ValidationError({"full_name": "Укажите имя соискателя."})
        if role == User.Role.EMPLOYER and not attrs.get("organization_name", "").strip():
            raise serializers.ValidationError({"organization_name": "Укажите название организации."})
        validate_password(attrs["password"])
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        role = validated_data["role"]
        full_name = validated_data.pop("full_name", "").strip()
        organization_name = validated_data.pop("organization_name", "").strip()
        validated_data.pop("role")
        user = User.objects.create_user(password=password, role=role, **validated_data)

        if role == User.Role.CANDIDATE:
            CandidateProfile.objects.create(user=user, full_name=full_name)
        else:
            organization = Organization.objects.create(owner=user, name=organization_name)
            OrganizationMembership.objects.create(
                organization=organization,
                user=user,
                role=OrganizationMembership.Role.MANAGER,
            )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role", "date_joined")
        read_only_fields = fields


class CandidateProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "user",
            "full_name",
            "phone",
            "location",
            "desired_position",
            "experience",
            "education",
            "resume_visibility",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user", "created_at", "updated_at")


class PublicCandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateProfile
        fields = ("id", "full_name", "location", "desired_position", "experience", "education")
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Organization
        fields = (
            "id",
            "owner_email",
            "name",
            "organization_type",
            "description",
            "address",
            "website",
            "contact_email",
            "contact_phone",
            "verification_status",
            "verification_note",
            "verified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "owner_email",
            "verification_status",
            "verification_note",
            "verified_at",
            "created_at",
            "updated_at",
        )


class PublicOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "organization_type", "description", "address", "website", "verification_status")
        read_only_fields = fields


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    user_email = serializers.EmailField(write_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ("id", "email", "user_email", "role", "created_at")
        read_only_fields = ("id", "email", "created_at")

    def validate_user_email(self, value):
        try:
            user = User.objects.get(email__iexact=value)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Пользователь с такой почтой не найден.") from exc
        if user.role != User.Role.EMPLOYER:
            raise serializers.ValidationError("Добавить можно только аккаунт работодателя.")
        self.user = user
        return value

    def create(self, validated_data):
        validated_data.pop("user_email")
        return OrganizationMembership.objects.create(user=self.user, **validated_data)
