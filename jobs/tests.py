from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CandidateResume, Organization, User
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

    def test_application_status_transitions_are_limited_by_role(self):
        candidate = self.register(
            "status-candidate@example.test",
            "candidate",
            full_name="Соискатель статусов",
        )
        self.client.force_authenticate(candidate)
        created = self.client.post(
            "/api/applications/",
            {"vacancy_id": self.vacancy.pk},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        application_id = created.data["id"]
        self.assertEqual(
            self.client.patch(
                f"/api/applications/{application_id}/",
                {"status": "accepted"},
                format="json",
            ).status_code,
            403,
        )

        self.client.force_authenticate(self.employer)
        invited = self.client.patch(
            f"/api/applications/{application_id}/",
            {"status": "invited"},
            format="json",
        )
        self.assertEqual(invited.status_code, 200, invited.data)
        self.assertEqual(
            self.client.patch(
                f"/api/applications/{application_id}/",
                {"status": "accepted"},
                format="json",
            ).status_code,
            400,
        )

        self.client.force_authenticate(candidate)
        accepted = self.client.patch(
            f"/api/applications/{application_id}/",
            {"status": "accepted"},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["status"], Application.Status.ACCEPTED)

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
        self.assertEqual(self.client.get("/api/vacancies/?region=saint-petersburg").data["count"], 0)
        self.assertEqual(self.client.get("/api/vacancies/?region=other").data["count"], 0)
        self.assertEqual(self.client.get("/api/vacancies/?region=mars").data["count"], 0)
        self.assertEqual(self.client.get("/api/vacancies/?category=prihod").data["count"], 1)

        self.vacancy.location = "Краснодар"
        self.vacancy.save(update_fields=["location"])
        self.assertEqual(self.client.get("/api/vacancies/?region=krasnodar").data["count"], 1)
        self.assertEqual(self.client.get("/api/vacancies/?region=Краснодарский%20край").data["count"], 1)

    def test_remote_and_map_radius_filters_work_on_site_and_api(self):
        remote_vacancy = Vacancy.objects.create(
            organization=self.organization,
            category=self.category,
            created_by=self.employer,
            title="Удалённый редактор",
            description="Описание удалённой вакансии",
            location="Россия",
            work_format=Vacancy.WorkFormat.REMOTE,
            status=Vacancy.Status.APPROVED,
            latitude=None,
            longitude=None,
        )
        self.vacancy.latitude = 55.75
        self.vacancy.longitude = 37.61
        self.vacancy.save(update_fields=["latitude", "longitude"])
        distant_vacancy = Vacancy.objects.create(
            organization=self.organization,
            category=self.category,
            created_by=self.employer,
            title="Вакансия далеко",
            description="Описание вакансии в отдалённом месте",
            location="Россия",
            latitude=56.0,
            longitude=37.61,
            status=Vacancy.Status.APPROVED,
        )
        self.client.force_authenticate(None)

        nearby = self.client.get("/vacancies/?latitude=55.75&longitude=37.61&radius=5")
        self.assertContains(nearby, self.vacancy.title)
        self.assertNotContains(nearby, distant_vacancy.title)
        self.assertNotContains(nearby, remote_vacancy.title)
        nearby_and_remote = self.client.get(
            "/vacancies/?latitude=55.75&longitude=37.61&radius=5&remote=1"
        )
        self.assertContains(nearby_and_remote, remote_vacancy.title)
        self.assertContains(nearby_and_remote, self.vacancy.title)
        self.assertNotContains(nearby_and_remote, distant_vacancy.title)
        self.assertContains(self.client.get("/vacancies/?remote=1"), remote_vacancy.title)
        self.assertContains(
            self.client.get("/vacancies/?remote=1"),
            'name="remote" value="1" checked',
            html=False,
        )
        invalid_radius = self.client.get(
            "/vacancies/?latitude=55.75&longitude=37.61&radius=201"
        )
        self.assertContains(invalid_radius, "от 1 до 200 км")

        self.assertEqual(self.client.get("/api/vacancies/?remote=true").data["count"], 1)
        self.assertEqual(self.client.get("/api/vacancies/?remote=false").data["count"], 2)
        self.assertEqual(
            self.client.get("/api/vacancies/?work_format=remote").data["count"],
            1,
        )
        self.assertEqual(self.client.get("/api/vacancies/?remote=maybe").status_code, 400)
        self.client.force_authenticate(self.employer)
        incomplete_coordinates = self.client.post(
            "/api/vacancies/",
            {
                "organization_id": self.organization.pk,
                "category_id": self.category.pk,
                "title": "Вакансия с неполной точкой",
                "description": "Описание вакансии с указанной только широтой.",
                "location": "Москва",
                "latitude": 55.75,
            },
            format="json",
        )
        self.assertEqual(incomplete_coordinates.status_code, 400)

    def test_region_suggestions_and_primary_categories_are_available_in_site_filters(self):
        response = self.client.get("/vacancies/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Республика Татарстан")
        self.assertContains(response, "Краснодарский край")
        self.assertContains(response, 'name="region"')
        self.assertContains(response, 'name="remote"')
        self.assertContains(response, "Поиск вакансий поблизости")
        self.assertContains(response, "<datalist", html=False)
        self.assertContains(response, "Медицина и уход")
        self.assertContains(response, "Волонтёрство")
        self.assertEqual(
            response.context["categories"].filter(
                slug__in=(
                    "education",
                    "social",
                    "healthcare",
                    "administration",
                    "facilities-maintenance",
                    "catering",
                    "clergy",
                    "volunteering",
                )
            ).count(),
            8,
        )

        homepage = self.client.get("/")
        self.assertContains(homepage, "Сахалинская область")
        self.assertContains(homepage, "Медицина и уход")
        self.assertContains(homepage, 'class="js-custom-select"')
        self.assertContains(homepage, "js/custom-select.js")

    def test_catalog_pages_show_only_published_vacancies(self):
        self.client.force_authenticate(None)
        Vacancy.objects.create(
            organization=self.organization,
            category=self.category,
            created_by=self.employer,
            title="Черновик не должен быть виден",
            description="Описание",
            location="Москва",
            status=Vacancy.Status.PENDING,
        )
        page = self.client.get("/vacancies/?region=moscow&q=Помощник")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Помощник по хозяйству")
        self.assertNotContains(page, "Черновик не должен быть виден")
        self.assertContains(self.client.get("/vacancies/?region=spb"), "По выбранным условиям вакансий пока нет.")
        self.assertEqual(self.client.get("/vacancies/?region=mars&page=abc").status_code, 200)
        self.assertEqual(self.client.get(f"/vacancies/{self.vacancy.pk}/").status_code, 200)
        detail = self.client.get(f"/vacancies/{self.vacancy.pk}/")
        self.assertContains(detail, 'aria-label="Хлебные крошки"')
        self.assertContains(detail, 'aria-label="Условия вакансии"')
        self.assertContains(detail, "Откликнуться на вакансию")
        self.assertContains(detail, '<ul class="vacancy-requirements">', html=False)
        draft = Vacancy.objects.get(title="Черновик не должен быть виден")
        self.assertEqual(self.client.get(f"/vacancies/{draft.pk}/").status_code, 404)

    def test_candidate_can_send_a_web_application_once(self):
        from django.test import Client

        candidate = self.register(
            "web-candidate@example.test",
            "candidate",
            full_name="Соискатель",
        )
        web = Client()
        response = web.get(f"/vacancies/{self.vacancy.pk}/apply/")
        self.assertRedirects(
            response,
            f"/login/?next=/vacancies/{self.vacancy.pk}/apply/",
            fetch_redirect_response=False,
        )

        web.force_login(candidate)
        empty_dialog = web.get(f"/vacancies/{self.vacancy.pk}/?apply=1")
        self.assertContains(empty_dialog, "Чтобы откликнуться, сначала создайте резюме.")
        self.assertContains(empty_dialog, "Создать новое резюме")
        resume = CandidateResume.objects.create(
            candidate=candidate.candidate_profile,
            title="Резюме редактора",
            desired_position="Редактор",
        )
        another_candidate = self.register(
            "another-candidate@example.test",
            "candidate",
            full_name="Другой соискатель",
        )
        another_resume = CandidateResume.objects.create(
            candidate=another_candidate.candidate_profile,
            title="Чужое резюме",
        )
        response = web.get(f"/vacancies/{self.vacancy.pk}/apply/")
        self.assertRedirects(
            response,
            f"/vacancies/{self.vacancy.pk}/?apply=1",
            fetch_redirect_response=False,
        )
        detail = web.get(f"/vacancies/{self.vacancy.pk}/?apply=1")
        self.assertContains(detail, "Сопроводительное письмо")
        self.assertContains(detail, "Резюме редактора")
        self.assertContains(detail, "Создать новое резюме")
        self.assertNotContains(detail, "Чужое резюме")
        response = web.post(
            f"/vacancies/{self.vacancy.pk}/apply/",
            {
                "resume": another_resume.pk,
                "cover_letter": "Мне интересна работа в вашей организации.",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Application.objects.filter(candidate=candidate.candidate_profile).exists())
        response = web.post(
            f"/vacancies/{self.vacancy.pk}/apply/",
            {
                "resume": resume.pk,
                "cover_letter": "Мне интересна работа в вашей организации.",
            },
        )
        self.assertRedirects(response, f"/vacancies/{self.vacancy.pk}/")
        application = Application.objects.get(
            vacancy=self.vacancy,
            candidate=candidate.candidate_profile,
        )
        self.assertEqual(application.resume, resume)
        self.assertEqual(application.cover_letter, "Мне интересна работа в вашей организации.")

        response = web.get(f"/vacancies/{self.vacancy.pk}/")
        self.assertContains(response, "Вы уже откликнулись на эту вакансию.")
        self.assertNotContains(response, "Откликнуться на вакансию")

    def test_employer_can_process_applications_and_candidate_can_answer_invitation(self):
        from django.test import Client

        candidate = self.register(
            "pipeline-candidate@example.test",
            "candidate",
            full_name="Кандидат процесса",
        )
        resume = CandidateResume.objects.create(
            candidate=candidate.candidate_profile,
            title="Резюме кандидата",
            desired_position="Помощник",
            experience="Опыт работы",
        )
        application = Application.objects.create(
            vacancy=self.vacancy,
            candidate=candidate.candidate_profile,
            resume=resume,
            cover_letter="Буду рад присоединиться.",
        )

        employer_web = Client()
        employer_web.force_login(self.employer)
        dashboard = employer_web.get("/employer/")
        self.assertContains(dashboard, "Отклики на вакансии")
        self.assertContains(dashboard, "Непросмотренные")
        self.assertContains(dashboard, "Кандидат процесса")
        self.assertContains(dashboard, "Помощник")

        self.assertRedirects(
            employer_web.post(
                f"/employer/applications/{application.pk}/status/",
                {"status": "reviewed"},
            ),
            "/employer/?applications=reviewed",
            fetch_redirect_response=False,
        )
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.REVIEWED)

        self.assertRedirects(
            employer_web.post(
                f"/employer/applications/{application.pk}/status/",
                {"status": "invited"},
            ),
            "/employer/?applications=invited",
            fetch_redirect_response=False,
        )
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.INVITED)

        candidate_web = Client()
        candidate_web.force_login(candidate)
        my_applications = candidate_web.get("/my-applications/")
        self.assertContains(my_applications, "Работодатель приглашает вас")
        self.assertEqual(
            candidate_web.post(
                f"/my-applications/{application.pk}/response/",
                {"status": "accepted"},
            ).status_code,
            302,
        )
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.ACCEPTED)
        self.assertContains(employer_web.get("/employer/?applications=accepted"), "Кандидат процесса")

        other_employer = self.register(
            "unrelated-employer@example.test",
            "employer",
            organization_name="Другая организация",
        )
        other_web = Client()
        other_web.force_login(other_employer)
        self.assertEqual(
            other_web.post(
                f"/employer/applications/{application.pk}/status/",
                {"status": "rejected"},
            ).status_code,
            404,
        )
        self.assertEqual(
            candidate_web.post(
                f"/my-applications/{application.pk}/response/",
                {"status": "rejected"},
            ).status_code,
            404,
        )

    def test_web_registration_resume_form_and_login_flow(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import Client

        web = Client()
        self.assertEqual(web.get("/resume/").status_code, 302)

        weak = web.post("/register/", {"full_name": "Иван", "email": "web@example.test", "password": "123"})
        self.assertEqual(weak.status_code, 200)
        self.assertFalse(User.objects.filter(email="web@example.test").exists())

        ok = web.post(
            "/register/",
            {"full_name": "Иван", "email": "web@example.test", "password": "Long-Test-Password-123!"},
        )
        self.assertRedirects(ok, "/resume/")
        user = User.objects.get(email="web@example.test")
        self.assertEqual(user.role, User.Role.CANDIDATE)

        form_data = {
            "surname": "Иванов",
            "first_name": "Иван",
            "patronymic": "",
            "phone": "+7 (900) 000-00-00",
            "location": "Москва",
            "desired_position": "Регент",
            "experience": "5 лет",
            "education": "",
            "resume_visibility": "public",
        }
        bad = web.post("/resume/", {**form_data, "resume_file": SimpleUploadedFile("cv.exe", b"MZ")})
        self.assertEqual(bad.status_code, 200)
        saved = web.post(
            "/resume/",
            {
                **form_data,
                "resume_file": SimpleUploadedFile("cv.pdf", b"%PDF-1.4 x"),
                "save_as_draft": "1",
            },
        )
        self.assertRedirects(saved, "/", fetch_redirect_response=False)
        profile = user.candidate_profile
        profile.refresh_from_db()
        self.assertEqual(profile.full_name, "Иван Иванов")
        self.assertEqual(profile.resume_file_name, "cv.pdf")
        self.assertEqual(profile.resume_visibility, "private")

        self.assertEqual(web.post("/logout/").status_code, 302)
        self.assertEqual(web.get("/resume/").status_code, 302)
        wrong = web.post("/login/", {"email": "web@example.test", "password": "wrong"})
        self.assertContains(wrong, "Неверная почта или пароль")
        good = web.post("/login/", {"email": "web@example.test", "password": "Long-Test-Password-123!"})
        self.assertRedirects(good, "/resume/")
        evil = web.post("/login/", {"email": "web@example.test", "password": "Long-Test-Password-123!", "next": "https://evil.test/"})
        self.assertRedirects(evil, "/resume/")

        web.post("/logout/")
        web.post("/login/", {"email": self.employer.email, "password": "Long-Test-Password-123!"})
        self.assertEqual(web.get("/resume/").status_code, 302)

    def test_employer_web_cabinet_flow(self):
        from django.test import Client

        web = Client()
        self.assertEqual(web.get("/employer/").status_code, 302)
        ok = web.post(
            "/register/employer/",
            {"organization_name": "Храм Тест", "email": "emp-web@example.test", "password": "Long-Test-Password-123!"},
        )
        self.assertRedirects(ok, "/employer/")
        user = User.objects.get(email="emp-web@example.test")
        self.assertEqual(user.role, User.Role.EMPLOYER)
        self.assertEqual(user.organizations.get().name, "Храм Тест")

        form_page = web.get("/employer/vacancies/new/")
        self.assertContains(form_page, 'class="js-custom-select"')
        self.assertContains(form_page, 'data-grouped-number="true"')

        data = {
            "category": self.category.pk,
            "title": "Звонарь",
            "location": "Москва",
            "employment_type": "full_time",
            "work_format": "onsite",
            "salary_min": "50000",
            "salary_max": "40000",
            "description": "Короткое",
            "requirements": "",
        }
        bad = web.post("/employer/vacancies/new/", data)
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(Vacancy.objects.filter(title="Звонарь").exists())

        data.update(
            salary_min="50 000",
            salary_max="60 000",
            description="Нужен звонарь для утренних и вечерних служб в храме города.",
        )
        self.assertEqual(web.post("/employer/vacancies/new/", data).status_code, 302)
        vacancy = Vacancy.objects.get(title="Звонарь")
        self.assertEqual(vacancy.status, Vacancy.Status.PENDING)
        self.assertEqual(vacancy.salary_min, 50000)
        self.assertEqual(vacancy.salary_max, 60000)
        self.assertEqual(vacancy.created_by, user)
        self.assertContains(web.get("/employer/"), "Звонарь")

        data["title"] = "Звонарь-помощник"
        data["work_format"] = "remote"
        self.assertEqual(web.post(f"/employer/vacancies/{vacancy.pk}/edit/", data).status_code, 302)
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.title, "Звонарь-помощник")
        self.assertEqual(vacancy.work_format, Vacancy.WorkFormat.REMOTE)

        other = Client()
        other.post(
            "/register/employer/",
            {"organization_name": "Чужая", "email": "other-emp@example.test", "password": "Long-Test-Password-123!"},
        )
        self.assertEqual(other.get(f"/employer/vacancies/{vacancy.pk}/edit/").status_code, 404)
        self.assertEqual(other.post(f"/employer/vacancies/{vacancy.pk}/close/").status_code, 404)

        self.assertEqual(web.post(f"/employer/vacancies/{vacancy.pk}/close/").status_code, 302)
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.status, Vacancy.Status.CLOSED)
        self.assertEqual(web.get(f"/employer/vacancies/{vacancy.pk}/edit/").status_code, 404)

        candidate = Client()
        candidate.post(
            "/register/",
            {"full_name": "Иван", "email": "cand2@example.test", "password": "Long-Test-Password-123!"},
        )
        self.assertEqual(candidate.get("/employer/").status_code, 302)

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
