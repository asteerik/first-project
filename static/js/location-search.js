document.addEventListener("DOMContentLoaded", function () {
    const mapElement = document.getElementById("vacancy-map");
    if (!mapElement) return;

    const radiusSlider = document.getElementById("map-radius");
    const radiusValue = document.getElementById("radius-value");
    const radiusInput = document.getElementById("radius-input");
    const mapForm = mapElement.closest("form");
    const latitudeInput = document.getElementById("latitude")
        || (mapForm && mapForm.elements.namedItem("latitude"));
    const longitudeInput = document.getElementById("longitude")
        || (mapForm && mapForm.elements.namedItem("longitude"));
    const locationText = document.getElementById("map-location");
    const detectButton = document.getElementById("detect-location");
    const defaultCenter = [55.75, 37.61];

    if (!latitudeInput || !longitudeInput) {
        if (locationText) {
            locationText.textContent = "Не удалось подключить поля координат карты.";
        }
        return;
    }

    const savedLatitude = Number(latitudeInput.value);
    const savedLongitude = Number(longitudeInput.value);
    const hasSavedPoint = latitudeInput.value !== "" && longitudeInput.value !== "";
    let selectedPoint = hasSavedPoint ? [savedLatitude, savedLongitude] : null;

    if (typeof ymaps === "undefined") {
        if (locationText) locationText.textContent = "Не удалось загрузить Яндекс Карты.";
        return;
    }

    ymaps.ready(function () {
        const map = new ymaps.Map("vacancy-map", {
            center: selectedPoint || defaultCenter,
            zoom: selectedPoint ? 10 : 4,
            controls: ["zoomControl", "fullscreenControl"]
        });

        let marker = null;
        let circle = null;
        let locationRequestId = 0;
        if (radiusSlider && selectedPoint) {
            circle = new ymaps.Circle(
                [selectedPoint, Number(radiusSlider.value) * 1000],
                {},
                {
                    fillColor: "#39734D33",
                    strokeColor: "#39734D",
                    strokeWidth: 2
                }
            );
            map.geoObjects.add(circle);
        }

        function isInRussia(coords) {
            return ymaps.geocode(coords, { results: 1 }).then(function (result) {
                const geoObject = result.geoObjects.get(0);
                if (!geoObject) return false;

                const metadata = geoObject.properties.get("metaDataProperty");
                const components = metadata
                    && metadata.GeocoderMetaData
                    && metadata.GeocoderMetaData.Address
                    && metadata.GeocoderMetaData.Address.Components;
                return Boolean(components && components.some(function (component) {
                    return component.kind === "country"
                        && ["Россия", "Российская Федерация"].includes(component.name);
                }));
            });
        }

        function updateLocation(coords) {
            const requestId = ++locationRequestId;
            if (locationText) locationText.textContent = "Проверяем, что точка находится в России...";

            return isInRussia(coords).then(function (isRussianPoint) {
                if (requestId !== locationRequestId) return false;
                if (!isRussianPoint) {
                    if (
                        Number(latitudeInput.value) === coords[0]
                        && Number(longitudeInput.value) === coords[1]
                    ) {
                        latitudeInput.value = "";
                        longitudeInput.value = "";
                        selectedPoint = null;
                        map.setCenter(defaultCenter, 4);
                    }
                    if (locationText) {
                        locationText.textContent = "Выберите точку на территории России.";
                    }
                    return false;
                }

                selectedPoint = coords;
                latitudeInput.value = coords[0];
                longitudeInput.value = coords[1];

                if (marker) {
                    map.geoObjects.remove(marker);
                }

                marker = new ymaps.Placemark(coords, {
                    balloonContent: "Выбранное местоположение"
                });
                map.geoObjects.add(marker);

                if (radiusSlider && !circle) {
                    circle = new ymaps.Circle(
                        [coords, Number(radiusSlider.value) * 1000],
                        {},
                        {
                            fillColor: "#39734D33",
                            strokeColor: "#39734D",
                            strokeWidth: 2
                        }
                    );
                    map.geoObjects.add(circle);
                }
                if (circle) circle.geometry.setCoordinates(coords);

                if (locationText) {
                    locationText.textContent =
                        "Выбранная точка: " +
                        coords[0].toFixed(4) + ", " +
                        coords[1].toFixed(4);
                }
                return true;
            }).catch(function () {
                if (requestId === locationRequestId && locationText) {
                    locationText.textContent = "Не удалось проверить точку по карте. Попробуйте ещё раз.";
                }
                return false;
            });
        }

        function updateRadius() {
            const radius = Number(radiusSlider.value);
            radiusValue.textContent = radius + " км";
            radiusInput.value = radius;
            if (circle) circle.geometry.setRadius(radius * 1000);
        }

        map.events.add("click", function (event) {
            updateLocation(event.get("coords"));
        });

        if (radiusSlider) radiusSlider.addEventListener("input", updateRadius);

        if (detectButton) detectButton.addEventListener("click", function () {
            if (!navigator.geolocation) {
                locationText.textContent = "Ваш браузер не поддерживает геолокацию.";
                return;
            }

            detectButton.disabled = true;
            const buttonLabel = detectButton.textContent;
            detectButton.textContent = "Определяем местоположение...";
            navigator.geolocation.getCurrentPosition(
                function (position) {
                    const coords = [
                        position.coords.latitude,
                        position.coords.longitude
                    ];

                    updateLocation(coords).then(function (isRussianPoint) {
                        if (isRussianPoint) map.setCenter(coords, 10);
                        detectButton.disabled = false;
                        detectButton.textContent = buttonLabel;
                    });
                },
                function (error) {
                    locationText.textContent = error.code === error.PERMISSION_DENIED
                        ? "Доступ к местоположению запрещён."
                        : "Не удалось определить местоположение.";
                    detectButton.disabled = false;
                    detectButton.textContent = buttonLabel;
                }
            );
        });

        if (selectedPoint) updateLocation(selectedPoint);
        if (radiusSlider) updateRadius();
    });
});