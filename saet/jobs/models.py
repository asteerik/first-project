from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from accounts.models import CandidateProfile, Organization


class Category(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)
    slug = models.SlugField("Слаг", max_length=140, unique=True)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "категория вакансий"
        verbose_name_plural = "категории вакансий"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vacancy(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Опубликована"
        REJECTED = "rejected", "Отклонена"
        CLOSED = "closed", "Закрыта"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Полная занятость"
        PART_TIME = "part_time", "Частичная занятость"
        TEMPORARY = "temporary", "Временная работа"
        VOLUNTEER = "volunteer", "Волонтёрство"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="vacancies",
        verbose_name="Организация",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="vacancies",
        verbose_name="Категория",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_vacancies",
        verbose_name="Автор",
    )
    title = models.CharField("Название должности", max_length=200)
    description = models.TextField("Описание", max_length=20000)
    requirements = models.TextField("Требования", blank=True, max_length=10000)
    location = models.CharField("Город или регион", max_length=120)
    employment_type = models.CharField(
        "Тип занятости",
        max_length=12,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    salary_min = models.PositiveIntegerField(
        "Зарплата от, руб.",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100000000)],
    )
    salary_max = models.PositiveIntegerField(
        "Зарплата до, руб.",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100000000)],
    )
    status = models.CharField(
        "Статус",
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    moderation_note = models.TextField("Комментарий модератора", blank=True)
    published_at = models.DateTimeField("Дата публикации", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "вакансия"
        verbose_name_plural = "вакансии"
        ordering = ["-published_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(salary_min__isnull=True)
                | Q(salary_max__isnull=True)
                | Q(salary_min__lte=models.F("salary_max")),
                name="vacancy_salary_min_lte_max",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "published_at"], name="vac_status_pub_idx"),
            models.Index(fields=["category", "status"], name="vac_cat_status_idx"),
            models.Index(fields=["location", "status"], name="vac_loc_status_idx"),
        ]

    def __str__(self):
        return self.title


class Application(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        REVIEWED = "reviewed", "Просмотрен"
        INVITED = "invited", "Приглашение"
        REJECTED = "rejected", "Отказ"
        WITHDRAWN = "withdrawn", "Отозван"

    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name="Вакансия",
    )
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name="Соискатель",
    )
    cover_letter = models.TextField("Сопроводительное письмо", blank=True, max_length=10000)
    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField("Отправлен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "отклик"
        verbose_name_plural = "отклики"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["vacancy", "candidate"], name="unique_candidate_vacancy"),
        ]
        indexes = [
            models.Index(fields=["vacancy", "status"], name="app_vac_status_idx"),
            models.Index(fields=["candidate", "created_at"], name="app_candidate_date_idx"),
        ]

    def __str__(self):
        return f"{self.candidate} — {self.vacancy}"


class Favorite(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Соискатель",
    )
    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name="Вакансия",
    )
    created_at = models.DateTimeField("Добавлена", auto_now_add=True)

    class Meta:
        verbose_name = "избранная вакансия"
        verbose_name_plural = "избранные вакансии"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["candidate", "vacancy"], name="unique_favorite_vacancy"),
        ]


class Complaint(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Новая"
        REVIEWING = "reviewing", "Рассматривается"
        RESOLVED = "resolved", "Решена"
        DISMISSED = "dismissed", "Отклонена"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="complaints",
        verbose_name="Заявитель",
    )
    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.PROTECT,
        related_name="complaints",
        verbose_name="Вакансия",
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="complaints",
        verbose_name="Организация",
        null=True,
        blank=True,
    )
    reason = models.CharField("Причина", max_length=120)
    details = models.TextField("Подробности", max_length=5000, blank=True)
    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.OPEN)
    resolution_note = models.TextField("Решение модератора", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    resolved_at = models.DateTimeField("Рассмотрена", null=True, blank=True)

    class Meta:
        verbose_name = "жалоба"
        verbose_name_plural = "жалобы"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(vacancy__isnull=False, organization__isnull=True)
                    | Q(vacancy__isnull=True, organization__isnull=False)
                ),
                name="complaint_exactly_one_target",
            ),
        ]

    def __str__(self):
        return f"Жалоба #{self.pk}: {self.reason}"


class ModerationLog(models.Model):
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="moderation_actions",
        verbose_name="Модератор",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="moderation_logs",
        verbose_name="Организация",
        null=True,
        blank=True,
    )
    vacancy = models.ForeignKey(
        Vacancy,
        on_delete=models.PROTECT,
        related_name="moderation_logs",
        verbose_name="Вакансия",
        null=True,
        blank=True,
    )
    action = models.CharField("Действие", max_length=40)
    note = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Дата действия", auto_now_add=True)

    class Meta:
        verbose_name = "запись модерации"
        verbose_name_plural = "журнал модерации"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["moderator", "created_at"], name="mod_user_date_idx")]

    def __str__(self):
        return f"{self.action} ({self.created_at:%Y-%m-%d %H:%M})"
