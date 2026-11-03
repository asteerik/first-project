from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Organization, User
from jobs.models import Application, Category, ModerationLog, Vacancy


class RecruitmentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employer = self.register(
            "employer@example.test",
            "employer",
            organization_name="Тестовый приход",
        )
        self.organization = Organization.objects.get(owner=self.employer)
        self.moderator = User.objects.create_user(
            "moderator@example.test",
            "Long-Test-Password-123!",
            role=User.Role.MODERATOR,
        )
        self.category = Category.objects.create(name="Приход", slug="prihod")
        self.moderate("organizations", self.organization.pk)
        self.client.force_authenticate(self.employer)
        response = self.client.post(
            "/api/vacancies/",
            {
                "organization_id": self.organization.pk,
                "category_id": self.category.pk,
                "title": "Помощник по хозяйству",
                "description": "Описание вакансии",
                "requirements": "Ответственность",
                "location": "Москва",
                "salary_min": 20000,
                "salary_max": 40000,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.vacancy = Vacancy.objects.get(pk=response.data["id"])
        self.assertEqual(self.vacancy.status, Vacancy.Status.PENDING)
        self.moderate("vacancies", self.vacancy.pk)

    def register(self, email, role, **extra_data):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": email,
                "password": "Long-Test-Password-123!",
                "role": role,
                **extra_data,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return User.objects.get(email=email)

    def moderate(self, target, pk):
        self.client.force_authenticate(self.moderator)
        response = self.client.post(
            f"/api/moderation/{target}/{pk}/",
            {"decision": "approve", "note": "Проверено"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_candidate_can_search_and_apply_but_resume_visibility_is_respected(self):
        self.client.force_authenticate(None)
        response = self.client.get("/api/vacancies/?q=Помощник&location=Моск&salary_min=20000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        public_vacancy = response.data["results"][0]
        self.assertNotIn("created_by", public_vacancy)
        self.assertEqual(public_vacancy["moderation_note"], "")

        invalid_filter = self.client.get("/api/vacancies/?salary_min=not-a-number")
        self.assertEqual(invalid_filter.status_code, 400)

        candidate = self.register(
            "candidate@example.test",
            "candidate",
            full_name="Тестовый соискатель",
        )
        profile = candidate.candidate_profile
        profile.experience = "Чувствительные сведения резюме"
        profile.save(update_fields=["experience"])

        self.client.force_authenticate(candidate)
        response = self.client.post(
            "/api/applications/",
            {"vacancy_id": self.vacancy.pk, "cover_letter": "Здравствуйте"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        duplicate = self.client.post(
            "/api/applications/",
            {"vacancy_id": self.vacancy.pk},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

        self.client.force_authenticate(self.employer)
        response = self.client.get("/api/applications/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        candidate_data = response.data["results"][0]["candidate"]
        self.assertEqual(candidate_data, {"id": profile.pk, "full_name": "Тестовый соискатель"})

        profile.resume_visibility = profile.ResumeVisibility.AFTER_APPLICATION
        profile.save(update_fields=["resume_visibility"])
        response = self.client.get("/api/applications/")
        self.assertEqual(
            response.data["results"][0]["candidate"]["experience"],
            "Чувствительные сведения резюме",
        )

    def test_registration_cannot_assign_moderator_role(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "attacker@example.test",
                "password": "Long-Test-Password-123!",
                "role": "moderator",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="attacker@example.test").exists())

    def test_login_returns_jwt_and_moderation_queue_is_role_restricted(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "employer@example.test", "password": "Long-Test-Password-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        self.client.force_authenticate(self.employer)
        forbidden = self.client.get("/api/moderation/vacancies/")
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.moderator)
        pending = Vacancy.objects.create(
            organization=self.organization,
            category=self.category,
            created_by=self.employer,
            title="Ожидает проверки",
            description="Описание",
            location="Москва",
            status=Vacancy.Status.PENDING,
        )
        queue = self.client.get("/api/moderation/vacancies/")
        self.assertEqual(queue.status_code, 200)
        self.assertEqual([item["id"] for item in queue.data["results"]], [pending.pk])

    def test_only_organization_members_can_change_vacancy_and_moderation_is_logged(self):
        outsider = User.objects.create_user(
            "outsider@example.test",
            "Long-Test-Password-123!",
            role=User.Role.EMPLOYER,
        )
        self.client.force_authenticate(outsider)
        response = self.client.patch(
            f"/api/vacancies/{self.vacancy.pk}/",
            {"title": "Изменено"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ModerationLog.objects.count(), 2)

    def test_vacancy_for_unverified_organization_cannot_be_published(self):
        unverified_organization = Organization.objects.create(
            owner=self.employer,
            name="Организация на проверке",
        )
        pending = Vacancy.objects.create(
            organization=unverified_organization,
            category=self.category,
            created_by=self.employer,
            title="Ожидает проверки",
            description="Описание",
            location="Москва",
            status=Vacancy.Status.PENDING,
        )
        self.client.force_authenticate(self.moderator)
        response = self.client.post(
            f"/api/moderation/vacancies/{pending.pk}/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Vacancy.Status.PENDING)

    def test_editing_verified_organization_requires_reverification(self):
        self.client.force_authenticate(self.employer)
        response = self.client.patch(
            f"/api/organizations/{self.organization.pk}/",
            {"name": "Изменённое название"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.organization.refresh_from_db()
        self.assertEqual(
            self.organization.verification_status,
            Organization.VerificationStatus.PENDING,
        )
        self.assertIsNone(self.organization.verified_at)
        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.status, Vacancy.Status.PENDING)
        self.client.force_authenticate(self.moderator)
        response = self.client.post(
            f"/api/moderation/organizations/{self.organization.pk}/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(None)
        response = self.client.get("/api/vacancies/")
        self.assertEqual(response.data["results"], [])
