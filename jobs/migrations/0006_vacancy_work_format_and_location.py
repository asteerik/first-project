from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0005_alter_application_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="vacancy",
            name="work_format",
            field=models.CharField(
                choices=[
                    ("onsite", "На месте"),
                    ("hybrid", "Гибридно"),
                    ("remote", "Удалённо"),
                ],
                default="onsite",
                max_length=10,
                verbose_name="Формат работы",
            ),
        ),
        migrations.AddField(
            model_name="vacancy",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[MinValueValidator(-90), MaxValueValidator(90)],
                verbose_name="Широта",
            ),
        ),
        migrations.AddField(
            model_name="vacancy",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[MinValueValidator(-180), MaxValueValidator(180)],
                verbose_name="Долгота",
            ),
        ),
        migrations.AddConstraint(
            model_name="vacancy",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("latitude__isnull", True),
                    ("longitude__isnull", True),
                )
                | models.Q(
                    ("latitude__isnull", False),
                    ("longitude__isnull", False),
                ),
                name="vacancy_coordinates_together",
            ),
        ),
    ]
