from django.urls import path

from .views import (
    ApplicationDetailView,
    ApplicationListCreateView,
    CategoryListView,
    ComplaintListCreateView,
    ComplaintModerationView,
    FavoriteDeleteView,
    FavoriteListCreateView,
    ModerationView,
    ModerationQueueView,
    VacancyCloseView,
    VacancyDetailView,
    VacancyListCreateView,
)
from .map_views import MapAddressSuggestionsView, MapReverseGeocodeView

urlpatterns = [
    path("map/address-suggestions/", MapAddressSuggestionsView.as_view(), name="map_address_suggestions"),
    path("map/reverse-geocode/", MapReverseGeocodeView.as_view(), name="map_reverse_geocode"),
    path("categories/", CategoryListView.as_view(), name="categories"),
    path("vacancies/", VacancyListCreateView.as_view(), name="vacancies"),
    path("vacancies/<int:pk>/", VacancyDetailView.as_view(), name="vacancy_detail"),
    path("vacancies/<int:pk>/close/", VacancyCloseView.as_view(), name="vacancy_close"),
    path("applications/", ApplicationListCreateView.as_view(), name="applications"),
    path("applications/<int:pk>/", ApplicationDetailView.as_view(), name="application_detail"),
    path("favorites/", FavoriteListCreateView.as_view(), name="favorites"),
    path("favorites/<int:pk>/", FavoriteDeleteView.as_view(), name="favorite_delete"),
    path("complaints/", ComplaintListCreateView.as_view(), name="complaints"),
    path("complaints/<int:pk>/moderate/", ComplaintModerationView.as_view(), name="complaint_moderate"),
    path("moderation/<str:target>/", ModerationQueueView.as_view(), name="moderation_queue"),
    path(
        "moderation/<str:target>/<int:pk>/",
        ModerationView.as_view(),
        name="moderation",
    ),
]
