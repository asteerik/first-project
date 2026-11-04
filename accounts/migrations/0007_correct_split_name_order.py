from django.db import migrations


def correct_split_name_order(apps, schema_editor):
    CandidateProfile = apps.get_model("accounts", "CandidateProfile")
    database = schema_editor.connection.alias
    profiles = CandidateProfile.objects.using(database).all()

    for profile in profiles.iterator():
        parts = profile.full_name.split()
        if (
            len(parts) > 1
            and profile.surname == parts[0][:80]
            and profile.first_name == parts[1][:80]
        ):
            profile.surname = parts[1][:80]
            profile.first_name = parts[0][:80]
            profile.save(using=database, update_fields=["surname", "first_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_candidateprofile_first_name_and_more"),
    ]

    operations = [
        migrations.RunPython(correct_split_name_order, migrations.RunPython.noop),
    ]
