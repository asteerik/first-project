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

    def test_favorites_are_private_unique_and_candidate_only(self):
        candidate = self.register("fav@example.test", "candidate", full_name="Соискатель")
        other = self.register("fav2@example.test", "candidate", full_name="Другой")

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/favorites/").status_code, 401)
        self.client.force_authenticate(self.employer)
        self.assertEqual(self.client.get("/api/favorites/").status_code, 403)

        self.client.force_authenticate(candidate)
        created = self.client.post("/api/favorites/", {"vacancy_id": self.vacancy.pk}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        duplicate = self.client.post("/api/favorites/", {"vacancy_id": self.vacancy.pk}, format="json")
        self.assertEqual(duplicate.status_code, 400)

        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/favorites/").data["count"], 0)
        self.assertEqual(self.client.delete(f"/api/favorites/{created.data['id']}/").status_code, 404)

        self.client.force_authenticate(candidate)
        self.assertEqual(self.client.delete(f"/api/favorites/{created.data['id']}/").status_code, 204)

    def test_complaints_are_visible_only_to_author_and_moderators(self):
        candidate = self.register("rep@example.test", "candidate", full_name="Заявитель")
        other = self.register("rep2@example.test", "candidate", full_name="Посторонний")

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/complaints/").status_code, 401)

        self.client.force_authenticate(candidate)
        both = self.client.post(
            "/api/complaints/",
            {
                "vacancy": self.vacancy.pk,
                "organization": self.organization.pk,
                "reason": "Спам",
                "details": "x",
            },
            format="json",
        )
        self.assertEqual(both.status_code, 400)
        created = self.client.post(
            "/api/complaints/",
            {"vacancy": self.vacancy.pk, "reason": "Спам", "details": "Подозрительная вакансия"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["status"], "open")

        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/complaints/").data["count"], 0)
        forbidden = self.client.patch(
            f"/api/complaints/{created.data['id']}/moderate/",
            {"status": "resolved"},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.moderator)
        self.assertEqual(self.client.get("/api/complaints/").data["count"], 1)
        bad = self.client.patch(
            f"/api/complaints/{created.data['id']}/moderate/",
            {"status": "open"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        logs_before = ModerationLog.objects.count()
        ok = self.client.patch(
            f"/api/complaints/{created.data['id']}/moderate/",
            {"status": "resolved", "resolution_note": "Проверено"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ModerationLog.objects.count(), logs_before + 1)

    def test_resume_file_validation_and_access_rules(self):
        import io
        import zipfile

        from django.core.files.uploadedfile import SimpleUploadedFile

        candidate = self.register("file@example.test", "candidate", full_name="С файлом")
        profile = candidate.candidate_profile
        self.client.force_authenticate(candidate)

        def upload(name, content):
            return self.client.put(
                "/api/profile/resume-file/",
                {"file": SimpleUploadedFile(name, content)},
                format="multipart",
            )

        self.assertEqual(upload("cv.exe", b"MZ").status_code, 400)
        self.assertEqual(upload("cv.pdf", b"not a pdf").status_code, 400)
        self.assertEqual(upload("cv.docx", b"not a zip").status_code, 400)
        self.assertEqual(upload("cv.pdf", b"%PDF-1.4" + b"0" * (5 * 1024 * 1024)).status_code, 400)
        self.assertEqual(self.client.put("/api/profile/resume-file/", {}, format="multipart").status_code, 400)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<w/>")
        self.assertEqual(upload("cv.docx", buffer.getvalue()).status_code, 200)

        response = upload("../evil.pdf", b"%PDF-1.4 content")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["has_resume_file"])
        self.assertNotIn("resume_file", response.data)
        profile.refresh_from_db()
        self.assertRegex(profile.resume_file.name, r"^resumes/[0-9a-f]{32}\.pdf$")

        own = self.client.get("/api/profile/resume-file/")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own["X-Content-Type-Options"], "nosniff")
        self.assertEqual(b"".join(own.streaming_content), b"%PDF-1.4 content")

        url = f"/api/candidates/{profile.pk}/resume-file/"
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.employer)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get("/api/profile/resume-file/").status_code, 403)

        self.client.force_authenticate(candidate)
        self.client.post("/api/applications/", {"vacancy_id": self.vacancy.pk}, format="json")
        profile.resume_visibility = profile.ResumeVisibility.AFTER_APPLICATION
        profile.save(update_fields=["resume_visibility"])
        self.client.force_authenticate(self.employer)
        employer_download = self.client.get(url)
        self.assertEqual(employer_download.status_code, 200)
        employer_download.close()

        self.client.force_authenticate(candidate)
        self.assertEqual(self.client.delete("/api/profile/resume-file/").status_code, 204)
        self.assertEqual(self.client.get("/api/profile/resume-file/").status_code, 404)

    def test_vacancy_filters_by_region_code(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/vacancies/?region=moscow").data["count"], 1)
        self.assertEqual(self.client.get("/api/vacancies/?region=spb").data["count"], 0)
        self.assertEqual(self.client.get("/api/vacancies/?region=other").data["count"], 0)
        self.assertEqual(self.client.get("/api/vacancies/?region=mars").status_code, 400)
        self.assertEqual(self.client.get("/api/vacancies/?category=prihod").data["count"], 1)

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
