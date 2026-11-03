from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Organization, User
from jobs.models import Category, Vacancy

DEMO_EMAIL = "demo-employer@example.invalid"

CATEGORIES = [
    ("Образование", "education"),
    ("Социальные услуги", "social"),
    ("Священнослужение", "clergy"),
]

ORGANIZATIONS = [
    ("Приход храма Покрова Пресвятой Богородицы", "Приход", "Москва"),
    ("Свято-Никольский монастырь", "Монастырь", "Нижний Новгород"),
    ("Православная гимназия во имя преподобного Сергия", "Образовательная организация", "Санкт-Петербург"),
]

VACANCIES = [
    (0, "clergy", "Регент церковного хора", "Москва", "full_time", 50000, 70000),
    (0, "social", "Помощник по хозяйству", "Москва", "part_time", 30000, 40000),
    (1, "social", "Трудник на монастырское подворье", "Нижний Новгород", "volunteer", None, None),
    (1, "social", "Повар для трапезной", "Нижний Новгород", "full_time", 45000, 60000),
    (2, "education", "Преподаватель Закона Божия", "Санкт-Петербург", "part_time", 35000, 50000),
    (2, "education", "Редактор приходского издания", "Санкт-Петербург", "temporary", 40000, 55000),
]


class Command(BaseCommand):
    help = "Создаёт демонстрационные категории, организации и вакансии (повторный запуск безопасен)."

    @transaction.atomic
    def handle(self, *args, **options):
        owner, _ = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={"role": User.Role.EMPLOYER},
        )
        if owner.has_usable_password():
            owner.set_unusable_password()
            owner.save(update_fields=["password"])

        titles = {title for _, _, title, *_ in VACANCIES}
        Vacancy.objects.filter(created_by=owner, applications__isnull=True).exclude(title__in=titles).delete()
        Organization.objects.filter(owner=owner, vacancies__isnull=True).exclude(
            name__in=[name for name, _, _ in ORGANIZATIONS]
        ).delete()
        legacy_slugs = ["prihod", "monastyr", "obrazovanie", "sluzhenie", "hozyaystvo", "media"]
        Category.objects.filter(slug__in=legacy_slugs, vacancies__isnull=True).delete()

        categories = {}
        for name, slug in CATEGORIES:
            categories[slug], _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})

        organizations = []
        now = timezone.now()
        for name, kind, city in ORGANIZATIONS:
            organization, _ = Organization.objects.get_or_create(
                owner=owner,
                name=name,
                defaults={
                    "organization_type": kind,
                    "address": city,
                    "description": "Демонстрационная организация.",
                    "verification_status": Organization.VerificationStatus.APPROVED,
                    "verified_at": now,
                },
            )
            organizations.append(organization)

        created = 0
        for org_index, slug, title, city, employment, salary_min, salary_max in VACANCIES:
            _, was_created = Vacancy.objects.update_or_create(
                organization=organizations[org_index],
                title=title,
                defaults={
                    "category": categories[slug],
                    "created_by": owner,
                    "description": "Демонстрационная вакансия для проверки интерфейса.",
                    "requirements": "Ответственность, доброжелательность.",
                    "location": city,
                    "employment_type": employment,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "status": Vacancy.Status.APPROVED,
                    "published_at": now,
                },
            )
            created += was_created

        self.stdout.write(self.style.SUCCESS(f"Готово. Новых вакансий: {created}."))
