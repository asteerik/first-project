import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

_DADATA_BASE_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/"
_REQUEST_TIMEOUT = 8


class DadataError(Exception):
    def __init__(self, code, message, status_code):
        self.code = code
        self.message = message
        self.status_code = status_code


def _dadata_request(method, payload):
    api_key = getattr(settings, "DADATA_API_KEY", "")
    if not api_key:
        raise DadataError(
            "not_configured",
            "Поиск адресов не настроен: добавьте DADATA_API_KEY в файл .env.",
            503,
        )

    request = Request(
        _DADATA_BASE_URL + method,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 429:
            raise DadataError("rate_limited", "Слишком много запросов. Попробуйте позже.", 429) from error
        if error.code in {401, 403}:
            logger.warning("DaData отклонила ключ для метода %s (HTTP %s).", method, error.code)
            raise DadataError(
                "invalid_key",
                "DaData отклонила API-ключ. Проверьте DADATA_API_KEY в файле .env.",
                503,
            ) from error
        logger.warning("DaData вернула HTTP %s для метода %s.", error.code, method)
        raise DadataError(
            "provider_error",
            "Российский сервис адресов временно недоступен. Попробуйте позже.",
            502,
        ) from error
    except (OSError, URLError, json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("Запрос к DaData не выполнен для метода %s: %s", method, type(error).__name__)
        raise DadataError(
            "provider_error",
            "Не удалось связаться с российским сервисом адресов. Попробуйте позже.",
            502,
        ) from error

    if not isinstance(data, dict) or not isinstance(data.get("suggestions"), list):
        logger.warning("DaData вернула ответ неожиданного формата для метода %s.", method)
        raise DadataError(
            "provider_error",
            "Российский сервис адресов вернул некорректный ответ.",
            502,
        )
    return data["suggestions"]


def _error_response(error):
    return Response(
        {"code": error.code, "detail": error.message},
        status=error.status_code,
    )


def _coordinates(data):
    try:
        latitude = float(data["geo_lat"])
        longitude = float(data["geo_lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude


class MapAddressSuggestionsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 3 or len(query) > 300:
            return Response(
                {"code": "invalid_query", "detail": "Введите от 3 до 300 символов."},
                status=400,
            )
        try:
            suggestions = _dadata_request(
                "suggest/address",
                {
                    "query": query,
                    "count": 5,
                    "locations": [{"country_iso_code": "RU"}],
                },
            )
        except DadataError as error:
            return _error_response(error)

        results = []
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                continue
            data = suggestion.get("data") or {}
            if not isinstance(data, dict):
                continue
            coords = _coordinates(data) if data.get("country_iso_code") == "RU" else None
            label = suggestion.get("value")
            if coords and isinstance(label, str) and label.strip():
                results.append(
                    {"label": label, "lat": coords[0], "lon": coords[1]}
                )
        return Response({"suggestions": results})


class MapReverseGeocodeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def get(self, request):
        try:
            latitude = float(request.query_params["lat"])
            longitude = float(request.query_params["lon"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"code": "invalid_coordinates", "detail": "Укажите координаты точки."},
                status=400,
            )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return Response(
                {"code": "invalid_coordinates", "detail": "Укажите корректные координаты."},
                status=400,
            )

        try:
            suggestions = _dadata_request(
                "geolocate/address",
                {
                    "lat": latitude,
                    "lon": longitude,
                    "count": 1,
                    "radius_meters": 1000,
                },
            )
        except DadataError as error:
            return _error_response(error)

        suggestion = suggestions[0] if suggestions else {}
        if not isinstance(suggestion, dict):
            suggestion = {}
        data = suggestion.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        return Response(
            {
                "country_code": data.get("country_iso_code", ""),
                "address": suggestion.get("value", ""),
            }
        )
