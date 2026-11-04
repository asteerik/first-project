from django.db import migrations


PRIMARY_CATEGORIES = (
    "education",
    "social",
    "healthcare",
    "administration",
    "facilities-maintenance",
    "catering",
    "clergy",
    "volunteering",
)

STANDARD_CATEGORIES = (
    "education",
    "social",
    "healthcare",
    "administration",
    "accounting-finance",
    "information-technology",
    "construction-repair",
    "facilities-maintenance",
    "catering",
    "cleaning",
    "transport",
    "culture",
    "publishing-media",
    "counseling",
    "legal",
    "procurement-logistics",
    "agriculture",
    "clergy",
    "monastery",
    "volunteering",
)


def select_primary_categories(apps, schema_editor):
    Category = apps.get_model("jobs", "Category")
    categories = Category.objects.using(schema_editor.connection.alias)
    categories.filter(slug__in=STANDARD_CATEGORIES).update(is_active=False)
    categories.filter(slug__in=PRIMARY_CATEGORIES).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_seed_categories"),
    ]

    operations = [
        migrations.RunPython(select_primary_categories, migrations.RunPython.noop),
    ]
