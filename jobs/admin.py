from django.contrib import admin

from .models import Application, Category, Complaint, Favorite, ModerationLog, Vacancy


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "category", "status", "created_at")
    list_filter = ("status", "employment_type", "category")
    search_fields = ("title", "organization__name", "location")
    readonly_fields = (
        "status",
        "moderation_note",
        "published_at",
        "created_at",
        "updated_at",
    )


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("vacancy", "candidate", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("vacancy__title", "candidate__full_name", "candidate__user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("candidate", "vacancy", "created_at")
    search_fields = ("candidate__full_name", "vacancy__title")
    readonly_fields = ("created_at",)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("reason", "reporter", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("reason", "reporter__email", "details")
    readonly_fields = ("status", "resolution_note", "resolved_at", "created_at")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("moderator", "action", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("moderator__email", "note", "action")
    readonly_fields = ("moderator", "organization", "vacancy", "action", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
