from django.db import migrations


CATEGORIES = (
    ("Образование", "education"),
    ("Социальные услуги", "social"),
    ("Медицина и уход", "healthcare"),
    ("Административная работа", "administration"),
    ("Бухгалтерия и финансы", "accounting-finance"),
    ("Информационные технологии", "information-technology"),
    ("Строительство и ремонт", "construction-repair"),
    ("Хозяйство и обслуживание", "facilities-maintenance"),
    ("Кухня и питание", "catering"),
    ("Уборка и клининг", "cleaning"),
    ("Водители и транспорт", "transport"),
    ("Культура и творчество", "culture"),
    ("Издательское дело и СМИ", "publishing-media"),
    ("Психология и консультирование", "counseling"),
    ("Юриспруденция", "legal"),
    ("Закупки и логистика", "procurement-logistics"),
    ("Сельское хозяйство", "agriculture"),
    ("Священнослужение", "clergy"),
    ("Работа в монастыре", "monastery"),
    ("Волонтёрство", "volunteering"),
)


def create_categories(apps, schema_editor):
    Category = apps.get_model("jobs", "Category")
    database = schema_editor.connection.alias
    for name, slug in CATEGORIES:
        categories = Category.objects.using(database)
        if not categories.filter(slug=slug).exists() and not categories.filter(name=name).exists():
            categories.create(name=name, slug=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_categories, migrations.RunPython.noop),
    ]
