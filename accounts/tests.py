from django.test import TestCase

from .models import CandidateProfile, CandidateResume, Organization, User


class CandidateResumePageTests(TestCase):
    def setUp(self):
        self.candidate = User.objects.create_user(
            "candidate@example.test",
            "Long-Test-Password-123!",
            role=User.Role.CANDIDATE,
        )
        self.other_candidate = User.objects.create_user(
            "other@example.test",
            "Long-Test-Password-123!",
            role=User.Role.CANDIDATE,
        )
        self.client.force_login(self.candidate)

    def create_resume(self):
        return self.client.post(
            "/resumes/new/",
            {
                "surname": "Смирнова",
                "first_name": "Анна",
                "patronymic": "Ивановна",
                "phone": "+7 (900) 000-00-00",
                "location": "Москва",
                "title": "Резюме редактора",
                "desired_position": "Редактор",
                "experience": "Опыт работы",
                "education": "Высшее образование",
                "resume_visibility": "private",
            },
        )

    def test_candidate_can_create_edit_and_delete_multiple_resumes(self):
        self.assertEqual(self.create_resume().status_code, 302)
        first_resume = CandidateResume.objects.get()
        self.assertEqual(first_resume.candidate.user, self.candidate)

        self.assertEqual(self.create_resume().status_code, 302)
        self.assertEqual(CandidateResume.objects.filter(candidate__user=self.candidate).count(), 2)

        response = self.client.post(
            f"/resumes/{first_resume.pk}/edit/",
            {
                "surname": "Смирнова",
                "first_name": "Анна",
                "patronymic": "Ивановна",
                "phone": "+7 (900) 000-00-00",
                "location": "Москва",
                "title": "Старший редактор",
                "desired_position": "Старший редактор",
                "experience": "Обновлённый опыт",
                "education": "Высшее образование",
                "resume_visibility": "private",
            },
        )
        self.assertEqual(response.status_code, 302)
        first_resume.refresh_from_db()
        self.assertEqual(first_resume.title, "Старший редактор")
        self.assertEqual(first_resume.candidate.full_name, "Анна Смирнова Ивановна")
        self.assertEqual(first_resume.candidate.phone, "+7 (900) 000-00-00")

        response = self.client.post(f"/resumes/{first_resume.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CandidateResume.objects.filter(pk=first_resume.pk).exists())
        self.assertEqual(CandidateResume.objects.filter(candidate__user=self.candidate).count(), 1)

    def test_other_candidates_cannot_view_download_edit_or_delete_resume(self):
        self.assertEqual(self.create_resume().status_code, 302)
        resume = CandidateResume.objects.get()
        self.client.force_login(self.other_candidate)

        self.assertEqual(self.client.get("/resumes/").status_code, 200)
        self.assertEqual(self.client.get(f"/resumes/{resume.pk}/edit/").status_code, 404)
        self.assertEqual(self.client.get(f"/resumes/{resume.pk}/download/").status_code, 404)
        self.assertEqual(self.client.post(f"/resumes/{resume.pk}/delete/").status_code, 404)
        self.assertTrue(CandidateResume.objects.filter(pk=resume.pk).exists())

    def test_empty_resume_list_shows_message_and_create_button(self):
        response = self.client.get("/resumes/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Активных резюме нет")
        self.assertContains(response, "Создать резюме")
        self.assertContains(response, "/resumes/new/")

    def test_resume_form_has_grouped_fields_autocomplete_and_upload_zone(self):
        response = self.client.get("/resumes/new/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Личная информация")
        self.assertContains(response, "Опыт и навыки")
        self.assertContains(response, "Настройки видимости")
        self.assertContains(response, "data-phone-mask")
        self.assertContains(response, "data-file-drop")
        self.assertContains(response, "position-suggestions")
        self.assertContains(response, "Сохранить черновик")

    def test_resume_form_validates_required_personal_data_and_sanitizes_rich_text(self):
        data = {
            "surname": "<script>alert(1)</script>",
            "first_name": "Анна",
            "patronymic": "",
            "phone": "+7 (900) 000-00-00",
            "location": "Москва",
            "title": "Редактор",
            "desired_position": "Редактор",
            "portfolio_url": "https://example.test/portfolio",
            "experience": (
                "<p>Навык <strong>редактирования</strong></p><script>alert(1)</script>"
                '<a href="javascript:alert(1)" onclick="alert(1)">ссылка</a>'
            ),
            "education": "<ul><li>МГУ</li></ul>",
            "resume_visibility": "public",
        }
        response = self.client.post("/resumes/new/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CandidateResume.objects.exists())

        data["surname"] = "Смирнова"
        data["phone"] = "+7 (900) 000-00-00abc"
        response = self.client.post("/resumes/new/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CandidateResume.objects.exists())

        data["phone"] = "+7 (900) 000-00-00"
        response = self.client.post("/resumes/new/", {**data, "save_as_draft": "1"})
        self.assertEqual(response.status_code, 302)
        resume = CandidateResume.objects.get()
        self.assertEqual(
            resume.experience,
            '<p>Навык <strong>редактирования</strong></p><a>ссылка</a>',
        )
        self.assertEqual(resume.portfolio_url, "https://example.test/portfolio")
        self.assertEqual(resume.resume_visibility, CandidateProfile.ResumeVisibility.PRIVATE)
        self.assertEqual(resume.candidate.full_name, "Анна Смирнова")
        self.assertEqual(resume.candidate.patronymic, "")

    def test_profile_menu_shows_candidate_name_and_theme_control(self):
        CandidateProfile.objects.create(
            user=self.candidate,
            full_name="Анна Смирнова",
        )

        response = self.client.get("/")
        self.assertContains(response, "Анна Смирнова")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Мои резюме")

    def test_employer_name_is_shown_in_profile_menu(self):
        employer = User.objects.create_user(
            "employer@example.test",
            "Long-Test-Password-123!",
            role=User.Role.EMPLOYER,
        )
        Organization.objects.create(owner=employer, name="Тестовый приход")
        self.client.force_login(employer)

        response = self.client.get("/")
        self.assertContains(response, "Тестовый приход")
        self.assertContains(response, "data-theme-toggle")
