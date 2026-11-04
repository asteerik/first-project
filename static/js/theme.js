(function () {
    const root = document.documentElement;
    let theme = "light";

    try {
        theme = localStorage.getItem("site-theme") === "dark" ? "dark" : "light";
    } catch (error) {
        console.warn("Не удалось прочитать сохранённую тему.", error);
    }

    function applyTheme(value) {
        root.dataset.theme = value;
        const themeColor = document.querySelector('meta[name="theme-color"]');
        if (themeColor) {
            themeColor.content = value === "dark" ? "#101010" : "#f6f6f0";
        }
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.setAttribute("aria-pressed", String(value === "dark"));
            button.textContent = value === "dark" ? "Светлая тема" : "Тёмная тема";
        });
    }

    applyTheme(theme);

    document.addEventListener("DOMContentLoaded", () => {
        applyTheme(theme);
        document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                theme = root.dataset.theme === "dark" ? "light" : "dark";
                applyTheme(theme);
                try {
                    localStorage.setItem("site-theme", theme);
                } catch (error) {
                    console.warn("Не удалось сохранить выбранную тему.", error);
                }
            });
        });
    });
})();
