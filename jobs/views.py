from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CandidateProfile, Organization, User
from accounts.permissions import (
    IsCandidate,
    IsModeratorOrAdmin,
    can_manage_organization,
    has_organization_access,
    user_can_view_resume,
)
from accounts.serializers import OrganizationSerializer
from .models import Application, Category, Complaint, Favorite, ModerationLog, Vacancy
from .serializers import (
    ApplicationSerializer,
    ApplicationStatusSerializer,
    CategorySerializer,
    ComplaintSerializer,
    FavoriteSerializer,
    VacancySerializer,
)


def parse_nonnegative_integer(value, parameter):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({parameter: "Укажите целое число."}) from exc
    if parsed < 0:
        raise ValidationError({parameter: "Значение не может быть отрицательным."})
    return parsed


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    queryset = Category.objects.filter(is_active=True)


class VacancyListCreateView(generics.ListCreateAPIView):
    serializer_class = VacancySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = Vacancy.objects.select_related("organization", "category", "created_by")
        if self.request.query_params.get("mine", "").lower() == "true":
            if not self.request.user.is_authenticated or self.request.user.role != User.Role.EMPLOYER:
                raise PermissionDenied("Список своих вакансий доступен работодателю.")
            queryset = queryset.filter(
                Q(organization__owner=self.request.user)
                | Q(organization__memberships__user=self.request.user)
            ).distinct()
        else:
            queryset = queryset.filter(
                status=Vacancy.Status.APPROVED,
                organization__verification_status=Organization.VerificationStatus.APPROVED,
            )

        search = self.request.query_params.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(requirements__icontains=search)
                | Q(organization__name__icontains=search)
            )
        location = self.request.query_params.get("location", "").strip()
        if location:
            queryset = queryset.filter(location__icontains=location)
        category = self.request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__slug=category)
        employment_type = self.request.query_params.get("employment_type", "").strip()
        if employment_type:
            if employment_type not in Vacancy.EmploymentType.values:
                raise ValidationError({"employment_type": "Неизвестный тип занятости."})
            queryset = queryset.filter(employment_type=employment_type)
        if "salary_min" in self.request.query_params:
            minimum = parse_nonnegative_integer(self.request.query_params["salary_min"], "salary_min")
            queryset = queryset.filter(Q(salary_max__gte=minimum) | Q(salary_max__isnull=True))
        if "salary_max" in self.request.query_params:
            maximum = parse_nonnegative_integer(self.request.query_params["salary_max"], "salary_max")
            queryset = queryset.filter(Q(salary_min__lte=maximum) | Q(salary_min__isnull=True))
        if {"salary_min", "salary_max"}.issubset(self.request.query_params):
            minimum = parse_nonnegative_integer(self.request.query_params["salary_min"], "salary_min")
            maximum = parse_nonnegative_integer(self.request.query_params["salary_max"], "salary_max")
            if minimum > maximum:
                raise ValidationError({"salary_max": "Максимальная зарплата меньше минимальной."})
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != User.Role.EMPLOYER:
            raise PermissionDenied("Публиковать вакансии может только работодатель.")
        organization = serializer.validated_data["organization"]
        if not has_organization_access(user, organization):
            raise PermissionDenied("Нет доступа к выбранной организации.")
        serializer.save(created_by=user, status=Vacancy.Status.PENDING)


class VacancyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VacancySerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        public = Q(
            status=Vacancy.Status.APPROVED,
            organization__verification_status=Organization.VerificationStatus.APPROVED,
        )
        if self.request.user.is_authenticated and self.request.user.role == User.Role.EMPLOYER:
            public |= Q(organization__owner=self.request.user) | Q(
                organization__memberships__user=self.request.user
            )
        return Vacancy.objects.select_related("organization", "category", "created_by").filter(public).distinct()

    def get_object(self):
        vacancy = super().get_object()
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            if (
                not self.request.user.is_authenticated
                or self.request.user.role != User.Role.EMPLOYER
            ):
                raise PermissionDenied("Изменять вакансии может только работодатель.")
            if not has_organization_access(self.request.user, vacancy.organization):
                raise PermissionDenied("Нет доступа к этой вакансии.")
        return vacancy

    def perform_update(self, serializer):
        vacancy = serializer.instance
        if vacancy.status == Vacancy.Status.CLOSED:
            raise ValidationError("Закрытую вакансию нельзя редактировать.")
        serializer.save(
            status=Vacancy.Status.PENDING,
            moderation_note="",
            published_at=None,
        )

    def perform_destroy(self, instance):
        instance.status = Vacancy.Status.CLOSED
        instance.published_at = None
        instance.save(update_fields=["status", "published_at", "updated_at"])


class VacancyCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        vacancy = get_object_or_404(Vacancy, pk=pk)
        if not has_organization_access(request.user, vacancy.organization):
            raise PermissionDenied("Нет доступа к этой вакансии.")
        vacancy.status = Vacancy.Status.CLOSED
        vacancy.published_at = None
        vacancy.save(update_fields=["status", "published_at", "updated_at"])
        return Response(VacancySerializer(vacancy).data)


class ApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related(
            "candidate",
            "candidate__user",
            "vacancy",
            "vacancy__organization",
        )
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(candidate__user=user)
        if user.role == User.Role.EMPLOYER:
            return queryset.filter(
                Q(vacancy__organization__owner=user)
                | Q(vacancy__organization__memberships__user=user)
            ).distinct()
        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != User.Role.CANDIDATE:
            raise PermissionDenied("Откликаться на вакансии может только соискатель.")
        try:
            candidate = user.candidate_profile
        except CandidateProfile.DoesNotExist as exc:
            raise ValidationError("Сначала заполните профиль соискателя.") from exc
        try:
            with transaction.atomic():
                serializer.save(candidate=candidate)
        except IntegrityError as exc:
            raise ValidationError({"vacancy_id": "Вы уже откликались на эту вакансию."}) from exc


class ApplicationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related(
            "candidate",
            "candidate__user",
            "vacancy",
            "vacancy__organization",
        )
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(candidate__user=user)
        if user.role == User.Role.EMPLOYER:
            return queryset.filter(
                Q(vacancy__organization__owner=user)
                | Q(vacancy__organization__memberships__user=user)
            ).distinct()
        return queryset.none()

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ApplicationStatusSerializer
        return ApplicationSerializer

    def perform_update(self, serializer):
        application = serializer.instance
        if self.request.user.role == User.Role.CANDIDATE:
            if serializer.validated_data.get("status") != Application.Status.WITHDRAWN:
                raise PermissionDenied("Соискатель может только отозвать свой отклик.")
            serializer.save(status=Application.Status.WITHDRAWN)
            return
        if self.request.user.role != User.Role.EMPLOYER:
            raise PermissionDenied("Недостаточно прав для изменения отклика.")
        if not has_organization_access(self.request.user, application.vacancy.organization):
            raise PermissionDenied("Нет доступа к этому отклику.")
        new_status = serializer.validated_data.get("status")
        if new_status not in (Application.Status.REVIEWED, Application.Status.INVITED, Application.Status.REJECTED):
            raise ValidationError({"status": "Работодатель может отметить отклик просмотренным, пригласить или отказать."})
        serializer.save()


class FavoriteListCreateView(generics.ListCreateAPIView):
    serializer_class = FavoriteSerializer
    permission_classes = [IsCandidate]

    def get_queryset(self):
        return Favorite.objects.filter(candidate__user=self.request.user).select_related(
            "vacancy",
            "vacancy__organization",
            "vacancy__category",
        )

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(candidate=self.request.user.candidate_profile)
        except IntegrityError as exc:
            raise ValidationError({"vacancy_id": "Эта вакансия уже добавлена в избранное."}) from exc
        except CandidateProfile.DoesNotExist as exc:
            raise ValidationError("Сначала заполните профиль соискателя.") from exc


class FavoriteDeleteView(APIView):
    permission_classes = [IsCandidate]

    def delete(self, request, pk):
        favorite = get_object_or_404(Favorite, pk=pk, candidate__user=request.user)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ComplaintListCreateView(generics.ListCreateAPIView):
    serializer_class = ComplaintSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in (User.Role.MODERATOR, User.Role.ADMIN):
            return Complaint.objects.select_related("reporter", "vacancy", "organization")
        return Complaint.objects.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class ComplaintModerationView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def patch(self, request, pk):
        with transaction.atomic():
            complaint = get_object_or_404(Complaint.objects.select_for_update(), pk=pk)
            new_status = request.data.get("status")
            if new_status not in (Complaint.Status.REVIEWING, Complaint.Status.RESOLVED, Complaint.Status.DISMISSED):
                raise ValidationError({"status": "Недопустимый статус жалобы."})
            complaint.status = new_status
            note = request.data.get("resolution_note", "")
            if not isinstance(note, str) or len(note) > 5000:
                raise ValidationError({"resolution_note": "Комментарий должен быть текстом не длиннее 5000 символов."})
            complaint.resolution_note = note.strip()
            if new_status in (Complaint.Status.RESOLVED, Complaint.Status.DISMISSED):
                complaint.resolved_at = timezone.now()
            else:
                complaint.resolved_at = None
            complaint.save(update_fields=["status", "resolution_note", "resolved_at"])
            ModerationLog.objects.create(
                moderator=request.user,
                organization=complaint.organization,
                vacancy=complaint.vacancy,
                action=f"complaint_{new_status}",
                note=complaint.resolution_note,
            )
        return Response(ComplaintSerializer(complaint).data)


class ModerationView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def post(self, request, target, pk):
        if target == "organizations":
            model = Organization
            choices = Organization.VerificationStatus
        elif target == "vacancies":
            model = Vacancy
            choices = Vacancy.Status
        else:
            raise ValidationError({"target": "Неизвестный тип объекта для проверки."})

        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            raise ValidationError({"decision": "Укажите approve или reject."})
        note = request.data.get("note", "")
        if not isinstance(note, str) or len(note) > 5000:
            raise ValidationError({"note": "Комментарий не должен превышать 5000 символов."})
        note = note.strip()

        with transaction.atomic():
            instance = get_object_or_404(model.objects.select_for_update(), pk=pk)
            if target == "organizations":
                if decision == "approve" and instance.verification_status != Organization.VerificationStatus.PENDING:
                    raise ValidationError({"decision": "Проверять можно только организацию со статусом «На проверке»."})
                new_status = (
                    choices.APPROVED if decision == "approve" else choices.REJECTED
                )
                instance.verification_status = new_status
                instance.verification_note = note
                instance.verified_at = timezone.now()
                instance.save(update_fields=["verification_status", "verification_note", "verified_at", "updated_at"])
                if new_status != Organization.VerificationStatus.APPROVED:
                    instance.vacancies.filter(status=Vacancy.Status.APPROVED).update(
                        status=Vacancy.Status.PENDING,
                        published_at=None,
                        updated_at=timezone.now(),
                    )
                organization, vacancy = instance, None
            else:
                if decision == "approve" and instance.status != Vacancy.Status.PENDING:
                    raise ValidationError({"decision": "Проверять можно только вакансию со статусом «На проверке»."})
                if instance.organization.verification_status != Organization.VerificationStatus.APPROVED and decision == "approve":
                    raise ValidationError({"decision": "Сначала необходимо проверить организацию."})
                new_status = choices.APPROVED if decision == "approve" else choices.REJECTED
                instance.status = new_status
                instance.moderation_note = note
                instance.published_at = timezone.now() if decision == "approve" else None
                instance.save(update_fields=["status", "moderation_note", "published_at", "updated_at"])
                organization, vacancy = None, instance
            ModerationLog.objects.create(
                moderator=request.user,
                organization=organization,
                vacancy=vacancy,
                action=f"{target}_{decision}",
                note=note,
            )
        serializer = OrganizationSerializer if target == "organizations" else VacancySerializer
        return Response(serializer(instance).data)


class ModerationQueueView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def get(self, request, target):
        status_filter = request.query_params.get("status", "")
        if target == "organizations":
            queryset = Organization.objects.all().order_by("created_at")
            allowed = Organization.VerificationStatus.values
            serializer_class = OrganizationSerializer
            field = "verification_status"
        elif target == "vacancies":
            queryset = Vacancy.objects.select_related("organization", "category").order_by("created_at")
            allowed = Vacancy.Status.values
            serializer_class = VacancySerializer
            field = "status"
        elif target == "complaints":
            queryset = Complaint.objects.select_related("reporter", "organization", "vacancy").order_by("created_at")
            allowed = Complaint.Status.values
            serializer_class = ComplaintSerializer
            field = "status"
        else:
            raise ValidationError({"target": "Неизвестный тип очереди модерации."})
        if status_filter:
            if status_filter not in allowed:
                raise ValidationError({"status": "Недопустимый статус."})
            queryset = queryset.filter(**{field: status_filter})
        else:
            pending_status = {
                "organizations": Organization.VerificationStatus.PENDING,
                "vacancies": Vacancy.Status.PENDING,
                "complaints": Complaint.Status.OPEN,
            }[target]
            queryset = queryset.filter(**{field: pending_status})
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(serializer_class(page, many=True).data)
        return Response(serializer_class(queryset, many=True).data)
