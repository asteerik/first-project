import os

from django.db import migrations


def copy_existing_resumes(apps, schema_editor):
    CandidateProfile = apps.get_model("accounts", "CandidateProfile")
    CandidateResume = apps.get_model("accounts", "CandidateResume")
    database = schema_editor.connection.alias

    profiles = CandidateProfile.objects.using(database).exclude(
        desired_position="",
        experience="",
        education="",
        resume_file="",
    )
    for profile in profiles.iterator():
        resume = CandidateResume(
            candidate_id=profile.pk,
            title=profile.desired_position[:120] or "Моё резюме",
            desired_position=profile.desired_position,
            experience=profile.experience,
            education=profile.education,
            resume_visibility=profile.resume_visibility,
            resume_file_name=profile.resume_file_name,
        )
        resume.save(using=database)

        if profile.resume_file and profile.resume_file.storage.exists(profile.resume_file.name):
            filename = profile.resume_file_name or os.path.basename(profile.resume_file.name)
            with profile.resume_file.open("rb") as source:
                resume.resume_file.save(filename, source, save=False)
            resume.resume_file_name = filename
            resume.save(using=database, update_fields=["resume_file", "resume_file_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_candidateresume"),
    ]

    operations = [
        migrations.RunPython(copy_existing_resumes, migrations.RunPython.noop),
    ]
