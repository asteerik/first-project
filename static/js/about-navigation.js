(() => {
    const navigation = document.querySelector(".about-toc");
    if (!navigation) {
        return;
    }

    const links = Array.from(navigation.querySelectorAll('a[href^="#"]'));
    const sections = links
        .map((link) => document.getElementById(link.hash.slice(1)))
        .filter(Boolean);

    const setActiveSection = (sectionId) => {
        links.forEach((link) => {
            const isActive = link.hash === `#${sectionId}`;
            link.classList.toggle("is-active", isActive);
            if (isActive) {
                link.setAttribute("aria-current", "location");
            } else {
                link.removeAttribute("aria-current");
            }
        });
    };

    const syncActiveSection = () => {
        const activationPoint = window.matchMedia("(max-width: 640px)").matches
            ? navigation.getBoundingClientRect().bottom + 12
            : Math.min(Math.max(100, window.innerHeight * 0.2), 160);
        const currentSection = sections.reduce((activeSection, section) => {
            if (section.getBoundingClientRect().top <= activationPoint) {
                return section;
            }
            return activeSection;
        }, sections[0]);
        if (currentSection) {
            setActiveSection(currentSection.id);
        }
    };

    navigation.addEventListener("click", (event) => {
        const link = event.target.closest('a[href^="#"]');
        if (!link || !navigation.contains(link)) {
            return;
        }

        const target = document.getElementById(link.hash.slice(1));
        if (!target) {
            return;
        }

        event.preventDefault();
        const mobileOffset = window.matchMedia("(max-width: 640px)").matches
            ? navigation.offsetHeight + 12
            : 24;
        const top = window.scrollY + target.getBoundingClientRect().top - mobileOffset;
        window.history.pushState(null, "", link.hash);
        window.scrollTo({
            top,
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? "auto"
                : "smooth",
        });
        target.focus({ preventScroll: true });
        setActiveSection(target.id);
    });

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(syncActiveSection, {
            rootMargin: "0px",
            threshold: 0,
        });

        sections.forEach((section) => observer.observe(section));
    }
    window.addEventListener("scroll", syncActiveSection, { passive: true });
    window.addEventListener("resize", syncActiveSection);

    const initialSection = window.location.hash.slice(1);
    if (sections.some((section) => section.id === initialSection)) {
        setActiveSection(initialSection);
    } else {
        syncActiveSection();
    }
})();
