(() => {
    const slider = document.querySelector("[data-hero-slider]");

    if (!slider) {
        return;
    }

    const slides = Array.from(slider.querySelectorAll("[data-hero-slide]"));
    const credit = slider.querySelector("[data-hero-credit]");
    const license = slider.querySelector("[data-hero-license]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let activeIndex = 0;
    let timerId;

    if (slides.length < 2 || !credit || !license) {
        return;
    }

    const showSlide = (index) => {
        activeIndex = (index + slides.length) % slides.length;

        slides.forEach((slide, slideIndex) => {
            slide.classList.toggle("is-active", slideIndex === activeIndex);
        });

        credit.href = slides[activeIndex].dataset.creditUrl;
        credit.textContent = slides[activeIndex].dataset.creditLabel;
        license.href = slides[activeIndex].dataset.licenseUrl;
        license.textContent = slides[activeIndex].dataset.licenseLabel;
    };

    const stopTimer = () => {
        window.clearInterval(timerId);
        timerId = undefined;
    };

    const startTimer = () => {
        stopTimer();

        if (!reduceMotion.matches && !document.hidden) {
            timerId = window.setInterval(() => showSlide(activeIndex + 1), 6000);
        }
    };

    document.addEventListener("visibilitychange", startTimer);
    reduceMotion.addEventListener("change", startTimer);
    startTimer();
})();
