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
    const detectButton = document.getElementById("detect-location");
    const addressInput = document.getElementById("map-address");
    const addressStatus = document.getElementById("map-address-status");
    const addressResults = document.getElementById("map-address-results");
    const savedLocationControls = document.querySelector("[data-saved-map-location]");
    const useSavedLocation = document.getElementById("use-saved-location");
    const forgetSavedLocation = document.getElementById("forget-saved-location");
    const savedLocationStatus = document.getElementById("saved-location-status");
    const savedLocationKey = "catalog-manual-location-v1";
    const defaultCenter = [55.75, 37.61];

    if (!latitudeInput || !longitudeInput) {
        if (locationText) {
            locationText.textContent = "Не удалось подключить поля координат карты.";
        }
        return;
    }

    const savedLatitude = Number(latitudeInput.value);
    const savedLongitude = Number(longitudeInput.value);
    const hasSavedPoint = latitudeInput.value !== "" && longitudeInput.value !== ""
        && Number.isFinite(savedLatitude) && Math.abs(savedLatitude) <= 90
        && Number.isFinite(savedLongitude) && Math.abs(savedLongitude) <= 180;
    const savedPoint = hasSavedPoint ? [savedLatitude, savedLongitude] : null;

    if (typeof L === "undefined") {
        if (locationText) locationText.textContent = navigator.onLine
            ? "Не удалось загрузить карту. Проверьте подключение к интернету."
            : "Нет подключения к интернету. Проверьте соединение и попробуйте снова.";
        console.error("Не удалось загрузить Leaflet.");
        return;
    }

    let map;
    try {
        map = L.map(mapElement).setView(savedPoint || defaultCenter, savedPoint ? 10 : 4);
        const tiles = L.tileLayer(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            {
                maxZoom: 19,
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }
        );
        tiles.on("tileerror", function () {
            if (mapError) {
                mapError.hidden = false;
                mapError.textContent = navigator.onLine
                    ? "Не удалось загрузить карту OpenStreetMap. Попробуйте позже."
                    : "Нет подключения к интернету. Карта недоступна.";
            }
        });
        tiles.addTo(map);
    } catch (error) {
        console.error("Ошибка инициализации карты Leaflet.");
        if (locationText) locationText.textContent = "Не удалось открыть карту. Попробуйте обновить страницу.";
        return;
    }

    let marker = null;
    let circle = null;
    let locationRequestId = 0;
    let locationPending = false;
    let activeController = null;
    const form = mapElement.closest("form");

    if (form) form.addEventListener("submit", function (event) {
        if (locationPending) {
            event.preventDefault();
            if (locationText) locationText.textContent = "Дождитесь проверки местоположения перед отправкой.";
        }
    });

    function clearLocation() {
        latitudeInput.value = "";
        longitudeInput.value = "";
        if (marker) map.removeLayer(marker);
        if (circle) map.removeLayer(circle);
        marker = null;
        circle = null;
    }

    function validCoordinates(coords) {
        return Array.isArray(coords) && coords.length === 2
            && coords.every(Number.isFinite)
            && Math.abs(coords[0]) <= 90 && Math.abs(coords[1]) <= 180;
    }

    function savedLocationError() {
        console.error("Не удалось использовать хранилище сохранённой точки.");
        savedLocationStatus.textContent = "Не удалось сохранить или прочитать точку в браузере. Проверьте настройки хранения данных.";
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
        useSavedLocation.hidden = !available;
        forgetSavedLocation.hidden = !available;
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

    async function photonRequest(path, params, controller) {
        let timedOut = false;
        const timeoutId = window.setTimeout(function () {
            timedOut = true;
            controller.abort();
        }, 15000);
        try {
            const response = await fetch("https://photon.komoot.io/" + path + "?" + params, {
                signal: controller.signal,
                referrerPolicy: "strict-origin-when-cross-origin"
            });
            if (!response.ok) {
                if (response.status === 401 || response.status === 403) throw new Error("forbidden");
                if (response.status === 429) throw new Error("limit");
                throw new Error("service_error");
            }
            const data = await response.json();
            if (!data || !Array.isArray(data.features)) throw new Error("service_error");
            return data.features;
        } catch (error) {
            if (timedOut) throw new Error("timeout");
            throw error;
        } finally {
            window.clearTimeout(timeoutId);
        }
    }

    function formatAddress(properties) {
        if (!properties || typeof properties !== "object") return "";
        const street = [properties.street, properties.housenumber].filter(Boolean).join(" ");
        return [properties.name, street, properties.city, properties.state, properties.country]
            .filter((value, index, values) => typeof value === "string" && value.trim() && values.indexOf(value) === index)
            .join(", ");
    }

    function invalidateRequest() {
        locationRequestId += 1;
        if (activeController) activeController.abort();
        activeController = null;
        locationPending = false;
        clearLocation();
        return locationRequestId;
    }

    async function updateLocation(coords, saveManually = false) {
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
            const features = await photonRequest("reverse", new URLSearchParams({
                lat: String(coords[0]), lon: String(coords[1]), limit: "1", lang: "en"
            }), controller);
            if (requestId !== locationRequestId) return false;
            const properties = features[0] && features[0].properties;
            const code = properties && properties.countrycode;
            if (typeof code !== "string" || !/^[a-z]{2}$/i.test(code)) throw new Error("no_country");
            if (code.toLowerCase() !== "ru") {
                if (locationText) locationText.textContent = "Выберите точку на территории России.";
                return false;
            }
            latitudeInput.value = coords[0].toFixed(6);
            longitudeInput.value = coords[1].toFixed(6);
            marker = L.marker(coords).addTo(map).bindPopup("Выбранное местоположение");
            if (radiusSlider) {
                circle = L.circle(coords, {
                    radius: Number(radiusSlider.value) * 1000,
                    color: "#39734d",
                    weight: 2,
                    fillColor: "#39734d",
                    fillOpacity: 0.2
                }).addTo(map);
            }
            const address = formatAddress(properties);
            if (saveManually) {
                saveManualLocation([Number(latitudeInput.value), Number(longitudeInput.value)]);
            }
            if (locationText) locationText.textContent = "Выбранная точка: "
                + coords[0].toFixed(4) + ", " + coords[1].toFixed(4)
                + (address ? " — " + address : "");
            return true;
        } catch (error) {
            if (requestId !== locationRequestId) return false;
            const reason = !navigator.onLine ? "offline"
                : error instanceof Error && ["timeout", "no_country", "forbidden", "limit", "service_error"].includes(error.message)
                    ? error.message : "geocoder_error";
            const messages = {
                offline: "Нет подключения к интернету. Проверка точки недоступна.",
                timeout: "Photon не ответил вовремя. Попробуйте ещё раз.",
                no_country: "Photon не определил страну этой точки. Выберите другую точку.",
                forbidden: "Photon отказал в доступе. Попробуйте позже.",
                limit: "Превышен лимит запросов Photon. Попробуйте позже.",
                service_error: "Сервис Photon временно недоступен. Попробуйте позже.",
                geocoder_error: "Не удалось проверить точку через Photon. Проверьте соединение."
            };
            if (locationText) locationText.textContent = messages[reason];
            console.error("Проверка точки Photon не выполнена. Категория:", reason);
            return false;
        } finally {
            if (requestId === locationRequestId) {
                activeController = null;
                locationPending = false;
            }
        }
    }

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
                    const features = await photonRequest("api/", new URLSearchParams({
                        q: query, limit: "5", lang: "en"
                    }), controller);
                    if (currentId !== searchId) return;
                    features.forEach(function (feature) {
                        const coordinates = feature && feature.geometry && feature.geometry.coordinates;
                        const label = formatAddress(feature && feature.properties);
                        if (!Array.isArray(coordinates) || !validCoordinates([coordinates[1], coordinates[0]]) || !label) return;
                        const button = document.createElement("button");
                        button.type = "button";
                        button.textContent = label;
                        button.addEventListener("click", async function () {
                            addressInput.value = label;
                            addressResults.replaceChildren();
                            addressStatus.textContent = "";
                            const coords = [coordinates[1], coordinates[0]];
                            if (await updateLocation(coords, true)) map.setView(coords, 14);
                        });
                        addressResults.append(button);
                    });
                    addressStatus.textContent = addressResults.children.length ? "Выберите адрес из списка." : "Адрес не найден.";
                } catch (error) {
                    if (currentId !== searchId) return;
                    const reason = error instanceof Error ? error.message : "network";
                    addressStatus.textContent = !navigator.onLine ? "Нет подключения к интернету."
                        : reason === "timeout" ? "Поиск адреса не ответил вовремя."
                        : reason === "limit" ? "Слишком много запросов. Попробуйте позже."
                        : "Не удалось найти адрес. Сервис Photon недоступен.";
                    console.error("Поиск адреса Photon не выполнен. Категория:", ["timeout", "limit", "forbidden", "service_error"].includes(reason) ? reason : "network");
                } finally {
                    if (currentId === searchId) searchController = null;
                }
            }, 800);
        });
        addressInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") event.preventDefault();
        });
    }

    function updateRadius() {
        const radius = Number(radiusSlider.value);
        radiusValue.textContent = radius + " км";
        radiusInput.value = radius;
        if (circle) circle.setRadius(radius * 1000);
    }

    map.on("click", function (event) {
        updateLocation([event.latlng.lat, event.latlng.wrap().lng], true);
    });

    if (radiusSlider) {
        radiusSlider.addEventListener("input", updateRadius);
        updateRadius();
    }

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

    const detectButtonLabel = detectButton && detectButton.textContent;
    if (detectButton) detectButton.addEventListener("click", function () {
        const requestId = invalidateRequest();
        detectButton.textContent = detectButtonLabel;
        if (!navigator.geolocation) {
            locationText.textContent = "Ваш браузер не поддерживает геолокацию. Выберите точку на карте.";
            return;
        }
        locationPending = true;
        detectButton.disabled = true;
        detectButton.textContent = "Определяем местоположение...";
        locationText.textContent = "Определяем местоположение...";
        navigator.geolocation.getCurrentPosition(
            async function (position) {
                let retry = false;
                try {
                    if (requestId !== locationRequestId) return;
                    const accuracy = position.coords.accuracy;
                    if (!Number.isFinite(accuracy) || accuracy < 0 || accuracy > 1000) {
                        locationPending = false;
                        locationText.textContent = "Не удалось точно определить ваше местоположение. Проверьте настройки геолокации устройства";
                        retry = true;
                        return;
                    }
                    const coords = [position.coords.latitude, position.coords.longitude];
                    if (await updateLocation(coords)) map.setView(coords, 10);
                } finally {
                    detectButton.disabled = false;
                    detectButton.textContent = retry ? "Повторить определение местоположения" : detectButtonLabel;
                }
            },
            function (error) {
                if (requestId === locationRequestId) {
                    locationPending = false;
                    if (error.code === error.PERMISSION_DENIED) {
                        locationText.textContent = "Доступ к местоположению запрещён. Разрешите геолокацию в браузере или выберите точку на карте.";
                    } else if (error.code === error.TIMEOUT) {
                        locationText.textContent = "Не удалось определить местоположение вовремя. Попробуйте ещё раз.";
                    } else {
                        locationText.textContent = "Не удалось получить координаты. Проверьте настройки геолокации или выберите точку на карте.";
                    }
                }
                detectButton.disabled = false;
                detectButton.textContent = detectButtonLabel;
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
    });

    if (savedPoint) updateLocation(savedPoint);
});
