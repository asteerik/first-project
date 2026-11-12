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
    const mapError = document.getElementById("map-error");
    const addressInput = document.getElementById("map-address");
    const addressStatus = document.getElementById("map-address-status");
    const addressResults = document.getElementById("map-address-results");
    const detectLocationButton = document.getElementById("detect-location");
    const geolocationStatus = document.getElementById("geolocation-status");
    const savedLocationControls = document.querySelector("[data-saved-map-location]");
    const useSavedLocation = document.getElementById("use-saved-location");
    const forgetSavedLocation = document.getElementById("forget-saved-location");
    const savedLocationStatus = document.getElementById("saved-location-status");
    const vacancyStatus = document.getElementById("map-vacancy-status");
    const openMapLink = document.getElementById("open-map");
    const savedLocationKey = "catalog-manual-location-v1";
    const defaultCenter = [55.75, 37.61];

    if (!latitudeInput || !longitudeInput) {
        if (locationText) locationText.textContent = "Не удалось подключить поля координат карты.";
        return;
    }

    const savedLatitude = Number(latitudeInput.value);
    const savedLongitude = Number(longitudeInput.value);
    const hasSavedPoint = latitudeInput.value !== "" && longitudeInput.value !== ""
        && Number.isFinite(savedLatitude) && Math.abs(savedLatitude) <= 90
        && Number.isFinite(savedLongitude) && Math.abs(savedLongitude) <= 180;
    const savedPoint = hasSavedPoint ? [savedLatitude, savedLongitude] : null;

    function showMapError(message) {
        if (mapError) {
            mapError.hidden = false;
            mapError.textContent = message;
        }
    }

    if (typeof L === "undefined") {
        showMapError(navigator.onLine
            ? "Не удалось загрузить библиотеку карты. Проверьте подключение и обновите страницу."
            : "Нет подключения к интернету. Карта недоступна.");
        if (locationText) locationText.textContent = "Не удалось открыть карту.";
        console.error("Не удалось загрузить Leaflet.");
        return;
    }

    let map;
    let selectedMarker = null;
    let radiusCircle = null;
    let accuracyCircle = null;
    let vacancyMarkerGroup = null;
    let vacancyMapItems = [];
    let activeController = null;
    let locationRequestId = 0;
    let locationPending = false;

    function validCoordinates(coords) {
        return Array.isArray(coords) && coords.length === 2
            && coords.every(Number.isFinite)
            && Math.abs(coords[0]) <= 90 && Math.abs(coords[1]) <= 180;
    }

    function updateOpenMapLink(coords) {
        if (!openMapLink || !map) return;
        const center = coords || map.getCenter();
        const zoom = map.getZoom();
        openMapLink.href = "https://www.openstreetmap.org/?mlat="
            + encodeURIComponent(center.lat || center[0])
            + "&mlon=" + encodeURIComponent(center.lng || center[1])
            + "#map=" + encodeURIComponent(zoom);
    }

    try {
        map = L.map(mapElement).setView(savedPoint || defaultCenter, savedPoint ? 10 : 4);
        const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        });
        tiles.on("tileerror", function () {
            showMapError(navigator.onLine
                ? "Не удалось загрузить карту OpenStreetMap. Попробуйте позже."
                : "Нет подключения к интернету. Карта недоступна.");
        });
        tiles.addTo(map);
    } catch (error) {
        console.error("Ошибка инициализации карты Leaflet.");
        showMapError("Не удалось открыть карту. Попробуйте обновить страницу.");
        return;
    }

    function savedLocationError() {
        console.error("Не удалось использовать хранилище сохранённой точки.");
        if (savedLocationStatus) {
            savedLocationStatus.textContent = "Не удалось сохранить или прочитать точку в браузере. Проверьте настройки хранения данных.";
        }
    }

    function readSavedLocation() {
        if (!savedLocationControls) return null;
        try {
            const raw = localStorage.getItem(savedLocationKey);
            if (!raw) return null;
            const point = JSON.parse(raw);
            if (!validCoordinates(point)) {
                localStorage.removeItem(savedLocationKey);
                savedLocationStatus.textContent = "Сохранённая точка некорректна. Выберите точку заново.";
                return null;
            }
            return point;
        } catch (error) {
            savedLocationError();
            return null;
        }
    }

    function showSavedLocationControls(available) {
        if (useSavedLocation) useSavedLocation.hidden = !available;
        if (forgetSavedLocation) forgetSavedLocation.hidden = !available;
    }

    function saveManualLocation(coords) {
        if (!savedLocationControls) return;
        try {
            localStorage.setItem(savedLocationKey, JSON.stringify(coords));
            showSavedLocationControls(true);
            savedLocationStatus.textContent = "Точка сохранена в этом браузере.";
        } catch (error) {
            savedLocationError();
        }
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, function (character) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;"
            }[character];
        });
    }

    function renderVacancyMarkers() {
        if (!vacancyMarkerGroup) return;
        vacancyMarkerGroup.clearLayers();
        const buckets = new Map();
        vacancyMapItems.forEach(function (item) {
            const point = map.project(item.coords, map.getZoom());
            const key = Math.floor(point.x / 64) + ":" + Math.floor(point.y / 64);
            if (!buckets.has(key)) buckets.set(key, []);
            buckets.get(key).push(item);
        });

        buckets.forEach(function (items) {
            if (items.length === 1) {
                L.marker(items[0].coords).bindPopup(items[0].content).addTo(vacancyMarkerGroup);
                return;
            }
            const center = [
                items.reduce((sum, item) => sum + item.coords[0], 0) / items.length,
                items.reduce((sum, item) => sum + item.coords[1], 0) / items.length
            ];
            const cluster = L.marker(center, {
                icon: L.divIcon({
                    className: "vacancy-map-cluster",
                    html: "<span>" + items.length + "</span>",
                    iconSize: [42, 42]
                })
            }).addTo(vacancyMarkerGroup);
            cluster.on("click", function () {
                const bounds = L.latLngBounds(items.map((item) => item.coords));
                if (map.getZoom() < map.getMaxZoom() && bounds.getNorthEast().distanceTo(bounds.getSouthWest()) > 1) {
                    map.fitBounds(bounds, { padding: [30, 30], maxZoom: map.getMaxZoom() });
                    return;
                }
                cluster.bindPopup(items.slice(0, 20).map((item) => item.content).join("<hr>")).openPopup();
            });
        });
    }

    function addVacancyMarkers() {
        const dataElement = document.getElementById("vacancy-map-markers");
        if (!dataElement) return [];

        let vacancies;
        try {
            vacancies = JSON.parse(dataElement.textContent);
        } catch (error) {
            console.error("Не удалось прочитать список вакансий для карты.");
            showMapError("Не удалось загрузить список вакансий на карту.");
            return [];
        }
        if (!Array.isArray(vacancies)) return [];

        vacancyMarkerGroup = L.layerGroup().addTo(map);
        const coordinates = [];
        vacancies.forEach(function (vacancy) {
            const coords = [Number(vacancy.latitude), Number(vacancy.longitude)];
            if (!validCoordinates(coords)) return;
            const content = "<strong>" + escapeHtml(vacancy.title || "Вакансия") + "</strong><br>"
                + escapeHtml(vacancy.organization || "") + "<br>"
                + escapeHtml(vacancy.location || "") + '<br><a href="'
                + escapeHtml(vacancy.url || "") + '">Подробнее о вакансии</a>';
            vacancyMapItems.push({ coords: coords, content: content });
            coordinates.push(coords);
        });
        renderVacancyMarkers();
        return coordinates;
    }

    async function addressApiRequest(path, params, controller) {
        let timedOut = false;
        const timeoutId = window.setTimeout(function () {
            timedOut = true;
            controller.abort();
        }, 12000);
        try {
            const response = await fetch(path + "?" + params, {
                signal: controller.signal,
                headers: { Accept: "application/json" }
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data && data.code ? data.code : "service_error");
            return data;
        } catch (error) {
            if (timedOut) throw new Error("timeout");
            throw error;
        } finally {
            window.clearTimeout(timeoutId);
        }
    }

    function clearSelectedLocation() {
        latitudeInput.value = "";
        longitudeInput.value = "";
        if (selectedMarker) map.removeLayer(selectedMarker);
        if (radiusCircle) map.removeLayer(radiusCircle);
        if (accuracyCircle) map.removeLayer(accuracyCircle);
        selectedMarker = null;
        radiusCircle = null;
        accuracyCircle = null;
    }

    function invalidateRequest() {
        locationRequestId += 1;
        if (activeController) activeController.abort();
        activeController = null;
        locationPending = false;
        clearSelectedLocation();
        return locationRequestId;
    }

    async function updateLocation(coords, saveManually, accuracyMeters) {
        const requestId = invalidateRequest();
        if (!validCoordinates(coords)) {
            if (locationText) locationText.textContent = "Не удалось получить корректные координаты точки.";
            return false;
        }

        locationPending = true;
        const controller = new AbortController();
        activeController = controller;
        if (locationText) locationText.textContent = "Проверяем, что точка находится в России...";
        try {
            const result = await addressApiRequest(
                "/api/map/reverse-geocode/",
                new URLSearchParams({ lat: String(coords[0]), lon: String(coords[1]) }),
                controller
            );
            if (requestId !== locationRequestId) return false;
            const countryCode = result && result.country_code;
            if (typeof countryCode !== "string" || !/^[a-z]{2}$/i.test(countryCode)) {
                throw new Error("no_country");
            }
            if (countryCode.toLowerCase() !== "ru") {
                if (locationText) locationText.textContent = "Выберите точку на территории России.";
                return false;
            }

            latitudeInput.value = coords[0].toFixed(6);
            longitudeInput.value = coords[1].toFixed(6);
            selectedMarker = L.marker(coords).addTo(map).bindPopup("Выбранное местоположение");
            if (radiusSlider) {
                radiusCircle = L.circle(coords, {
                    radius: Number(radiusSlider.value) * 1000,
                    color: "#39734d",
                    weight: 2,
                    fillColor: "#39734d",
                    fillOpacity: 0.2
                }).addTo(map);
            }
            if (Number.isFinite(accuracyMeters) && accuracyMeters > 0) {
                accuracyCircle = L.circle(coords, {
                    radius: accuracyMeters,
                    color: "#b29255",
                    weight: 2,
                    fillColor: "#b29255",
                    fillOpacity: 0.16
                }).addTo(map);
            }
            if (saveManually) saveManualLocation([Number(latitudeInput.value), Number(longitudeInput.value)]);
            if (locationText) {
                locationText.textContent = "Выбранная точка: "
                    + coords[0].toFixed(4) + ", " + coords[1].toFixed(4)
                    + (result.address ? " — " + result.address : "")
                    + (Number.isFinite(accuracyMeters) ? ". Точность GPS: ±" + Math.round(accuracyMeters) + " м." : "");
            }
            updateOpenMapLink(coords);
            return true;
        } catch (error) {
            if (requestId !== locationRequestId) return false;
            const reason = !navigator.onLine ? "offline"
                : error instanceof Error && [
                    "timeout", "no_country", "not_configured", "invalid_key",
                    "rate_limited", "provider_error", "service_error"
                ].includes(error.message) ? error.message : "geocoder_error";
            const messages = {
                offline: "Нет подключения к интернету. Проверка точки недоступна.",
                timeout: "DaData не ответила вовремя. Попробуйте ещё раз.",
                no_country: "Не удалось подтвердить, что точка находится в России. Выберите другую точку.",
                not_configured: "Поиск адресов не настроен: добавьте ключ DaData в .env.",
                invalid_key: "DaData отклонила API-ключ. Проверьте DADATA_API_KEY в .env.",
                rate_limited: "Слишком много запросов. Попробуйте позже.",
                provider_error: "DaData временно недоступна. Попробуйте позже.",
                service_error: "Сервис адресов временно недоступен. Попробуйте позже.",
                geocoder_error: "Не удалось проверить точку. Проверьте соединение."
            };
            if (locationText) locationText.textContent = messages[reason];
            console.error("Проверка точки через DaData не выполнена. Категория:", reason);
            return false;
        } finally {
            if (requestId === locationRequestId) {
                activeController = null;
                locationPending = false;
            }
        }
    }

    if (mapForm) mapForm.addEventListener("submit", function (event) {
        if (locationPending) {
            event.preventDefault();
            if (locationText) locationText.textContent = "Дождитесь проверки местоположения перед отправкой.";
        }
    });

    if (radiusSlider) {
        radiusSlider.addEventListener("input", function () {
            const radius = Number(radiusSlider.value);
            if (radiusValue) radiusValue.textContent = radius + " км";
            if (radiusInput) radiusInput.value = radius;
            if (radiusCircle) radiusCircle.setRadius(radius * 1000);
        });
        radiusSlider.dispatchEvent(new Event("input"));
    }

    map.on("click", function (event) {
        updateLocation([event.latlng.lat, event.latlng.lng], true);
    });
    if (detectLocationButton) {
        detectLocationButton.addEventListener("click", function () {
            if (!navigator.geolocation) {
                if (geolocationStatus) geolocationStatus.textContent = "Этот браузер не поддерживает определение местоположения.";
                return;
            }
            if (!window.isSecureContext) {
                if (geolocationStatus) geolocationStatus.textContent = "Определение местоположения доступно только на защищённом HTTPS-соединении.";
                return;
            }

            detectLocationButton.disabled = true;
            if (geolocationStatus) geolocationStatus.textContent = "Определяем местоположение...";
            try {
                navigator.geolocation.getCurrentPosition(async function (position) {
                    try {
                        const coords = [position.coords.latitude, position.coords.longitude];
                        if (!Number.isFinite(position.coords.accuracy) || position.coords.accuracy > 1000) {
                            if (geolocationStatus) geolocationStatus.textContent = "Точность определения ниже 1 км. Попробуйте ещё раз или выберите точку на карте.";
                            return;
                        }
                        const confirmed = await updateLocation(coords, false, position.coords.accuracy);
                        if (confirmed) {
                            map.setView(coords, 12);
                            if (geolocationStatus) geolocationStatus.textContent = "Местоположение определено.";
                        } else if (geolocationStatus) {
                            geolocationStatus.textContent = "Не удалось подтвердить местоположение. Проверьте сообщение над картой.";
                        }
                    } finally {
                        detectLocationButton.disabled = false;
                    }
                }, function (error) {
                    const messages = {
                        1: "Доступ к местоположению запрещён. Разрешите его в настройках браузера.",
                        2: "Не удалось определить местоположение. Проверьте GPS и подключение к интернету.",
                        3: "Определение местоположения заняло слишком много времени. Попробуйте ещё раз."
                    };
                    if (geolocationStatus) {
                        geolocationStatus.textContent = messages[error.code]
                            || "Не удалось определить местоположение. Выберите точку на карте.";
                    }
                    detectLocationButton.disabled = false;
                }, {
                    enableHighAccuracy: true,
                    maximumAge: 0,
                    timeout: 15000
                });
            } catch (error) {
                detectLocationButton.disabled = false;
                if (geolocationStatus) {
                    geolocationStatus.textContent = "Браузер не смог запустить определение местоположения. Проверьте настройки доступа.";
                }
                console.error("Не удалось запустить браузерную геолокацию.", error);
            }
        });
    }
    map.on("moveend", function () {
        updateOpenMapLink();
    });
    map.on("zoomend", renderVacancyMarkers);

    const vacancyCoordinates = addVacancyMarkers();
    if (vacancyStatus && vacancyCoordinates.length === 0 && vacancyStatus.textContent.trim() === "") {
        vacancyStatus.textContent = "Для подходящих вакансий не указаны координаты; они не отмечены на карте.";
    }
    if (!savedPoint && vacancyCoordinates.length) {
        const bounds = L.latLngBounds(vacancyCoordinates);
        map.fitBounds(bounds, { padding: [24, 24], maxZoom: vacancyCoordinates.length === 1 ? 12 : 10 });
    }
    updateOpenMapLink();

    if (savedLocationControls) {
        showSavedLocationControls(Boolean(readSavedLocation()));
        useSavedLocation.addEventListener("click", async function () {
            const point = readSavedLocation();
            if (!point) {
                showSavedLocationControls(false);
                return;
            }
            if (await updateLocation(point)) map.setView(point, 10);
        });
        forgetSavedLocation.addEventListener("click", function () {
            try {
                localStorage.removeItem(savedLocationKey);
                showSavedLocationControls(false);
                savedLocationStatus.textContent = "Сохранённая точка удалена из браузера.";
            } catch (error) {
                savedLocationError();
            }
        });
    }

    if (savedPoint) updateLocation(savedPoint);

    if (addressInput && addressStatus && addressResults) {
        let searchTimer;
        let searchController;
        let searchId = 0;
        addressInput.addEventListener("input", function () {
            window.clearTimeout(searchTimer);
            if (searchController) searchController.abort();
            const currentId = ++searchId;
            addressResults.replaceChildren();
            const query = addressInput.value.trim();
            addressStatus.textContent = "";
            if (query.length < 3) return;
            addressStatus.textContent = "Поиск адреса...";
            searchTimer = window.setTimeout(async function () {
                const controller = new AbortController();
                searchController = controller;
                try {
                    const data = await addressApiRequest(
                        "/api/map/address-suggestions/",
                        new URLSearchParams({ q: query }),
                        controller
                    );
                    if (currentId !== searchId) return;
                    (data.suggestions || []).forEach(function (suggestion) {
                        const coords = [Number(suggestion.lat), Number(suggestion.lon)];
                        const label = suggestion.label;
                        if (!validCoordinates(coords) || !label) return;
                        const button = document.createElement("button");
                        button.type = "button";
                        button.textContent = label;
                        button.addEventListener("click", async function () {
                            addressInput.value = label;
                            addressResults.replaceChildren();
                            addressStatus.textContent = "";
                            if (await updateLocation(coords, true)) map.setView(coords, 14);
                        });
                        addressResults.append(button);
                    });
                    addressStatus.textContent = addressResults.children.length
                        ? "Выберите адрес из списка."
                        : "Адрес не найден.";
                } catch (error) {
                    if (currentId !== searchId) return;
                    const reason = error instanceof Error ? error.message : "network";
                    addressStatus.textContent = !navigator.onLine ? "Нет подключения к интернету."
                        : reason === "timeout" ? "Поиск адреса не ответил вовремя."
                        : reason === "rate_limited" ? "Слишком много запросов. Попробуйте позже."
                        : reason === "not_configured" ? "Поиск адресов не настроен: добавьте ключ DaData в .env."
                        : reason === "invalid_key" ? "DaData отклонила API-ключ. Проверьте DADATA_API_KEY в .env."
                        : reason === "provider_error" ? "DaData временно недоступна."
                        : "Не удалось найти адрес. Проверьте подключение и настройки сервиса.";
                    console.error("Поиск адреса через DaData не выполнен. Категория:", reason);
                } finally {
                    if (currentId === searchId) searchController = null;
                }
            }, 500);
        });
        addressInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") event.preventDefault();
        });
    }
});
