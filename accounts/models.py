from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Для пользователя требуется адрес электронной почты.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Соискатель"
        EMPLOYER = "employer", "Работодатель"
        MODERATOR = "moderator", "Модератор"
        ADMIN = "admin", "Администратор"

    email = models.EmailField("Электронная почта", unique=True)
    role = models.CharField("Роль", max_length=20, choices=Role.choices)
    is_active = models.BooleanField("Активен", default=True)
    is_staff = models.BooleanField("Доступ в админ-панель", default=False)
    date_joined = models.DateTimeField("Дата регистрации", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ["email"]

    def __str__(self):
        return self.email


class CandidateProfile(models.Model):
    class ResumeVisibility(models.TextChoices):
        PRIVATE = "private", "Только мне"
        AFTER_APPLICATION = "after_application", "Работодателям после отклика"
        PUBLIC = "public", "Публичный профиль"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
        verbose_name="Пользователь",
    )
    full_name = models.CharField("ФИО", max_length=200)
    phone = models.CharField(
        "Телефон",
        max_length=32,
        blank=True,
        validators=[RegexValidator(r"^[0-9+() .-]*$", "Укажите корректный номер телефона.")],
    )
    location = models.CharField("Город или регион", max_length=120, blank=True)
    desired_position = models.CharField("Желаемая должность", max_length=150, blank=True)
    experience = models.TextField("Опыт и навыки", blank=True)
    education = models.TextField("Образование", blank=True)
    resume_visibility = models.CharField(
        "Видимость резюме",
        max_length=24,
        choices=ResumeVisibility.choices,
        default=ResumeVisibility.PRIVATE,
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "профиль соискателя"
        verbose_name_plural = "профили соискателей"

    def __str__(self):
        return self.full_name


class Organization(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Проверена"
        REJECTED = "rejected", "Отклонена"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizations",
        verbose_name="Владелец",
    )
    name = models.CharField("Название", max_length=200)
    organization_type = models.CharField("Тип организации", max_length=100, blank=True)
    description = models.TextField("Описание", blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    website = models.URLField("Сайт", blank=True)
    contact_email = models.EmailField("Контактная почта", blank=True)
    contact_phone = models.CharField(
        "Контактный телефон",
        max_length=32,
        blank=True,
        validators=[RegexValidator(r"^[0-9+() .-]*$", "Укажите корректный номер телефона.")],
    )
    verification_status = models.CharField(
        "Статус проверки",
        max_length=12,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verification_note = models.TextField("Комментарий проверки", blank=True)
    verified_at = models.DateTimeField("Дата проверки", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "организация"
        verbose_name_plural = "организации"
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "Управляющий"
        RECRUITER = "recruiter", "Специалист по подбору"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Организация",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
        verbose_name="Пользователь",
    )
    role = models.CharField("Роль в организации", max_length=12, choices=Role.choices)
    created_at = models.DateTimeField("Добавлен", auto_now_add=True)

    class Meta:
        verbose_name = "участник организации"
        verbose_name_plural = "участники организаций"
        ordering = ["organization", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_member",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.organization}"
