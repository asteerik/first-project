from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_correct_split_name_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidateresume",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[MinValueValidator(-90), MaxValueValidator(90)],
                verbose_name="Широта желаемого места работы",
            ),
        ),
        migrations.AddField(
            model_name="candidateresume",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[MinValueValidator(-180), MaxValueValidator(180)],
                verbose_name="Долгота желаемого места работы",
            ),
        ),
        migrations.AddField(
            model_name="candidateresume",
            name="preferred_radius_km",
            field=models.PositiveSmallIntegerField(
                default=50,
                validators=[MinValueValidator(1), MaxValueValidator(200)],
                verbose_name="Желаемый радиус поиска, км",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidateresume",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("latitude__isnull", True),
                    ("longitude__isnull", True),
                )
                | models.Q(
                    ("latitude__isnull", False),
                    ("longitude__isnull", False),
                ),
                name="resume_coordinates_together",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidateresume",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("preferred_radius_km__gte", 1),
                    ("preferred_radius_km__lte", 200),
                ),
                name="resume_radius_1_to_200",
            ),
        ),
    ]
