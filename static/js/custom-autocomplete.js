(() => {
    const inputs = document.querySelectorAll("input[data-custom-autocomplete][list]");
    let generatedId = 0;

    inputs.forEach((input) => {
        const datalist = document.getElementById(input.getAttribute("list"));
        if (!datalist) {
            return;
        }

        const options = Array.from(datalist.options)
            .map((option) => option.value.trim())
            .filter(Boolean);
        if (!options.length) {
            return;
        }

        generatedId += 1;
        const wrapper = document.createElement("div");
        wrapper.className = "custom-autocomplete";
        const listbox = document.createElement("div");
        listbox.className = "custom-autocomplete__listbox";
        listbox.id = `custom-autocomplete-listbox-${generatedId}`;
        listbox.setAttribute("role", "listbox");
        listbox.hidden = true;
        input.parentNode.insertBefore(wrapper, input);
        wrapper.append(input, listbox);

        input.removeAttribute("list");
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-controls", listbox.id);
        input.setAttribute("aria-expanded", "false");

        let matches = [];
        let activeIndex = -1;

        const updateListHeight = () => {
            if (!input.hasAttribute("data-autocomplete-viewport") || listbox.hidden) {
                return;
            }
            const viewport = window.visualViewport;
            const viewportBottom = viewport ? viewport.offsetTop + viewport.height : window.innerHeight;
            const availableHeight = Math.max(0, viewportBottom - listbox.getBoundingClientRect().top - 8);
            listbox.style.setProperty("--city-list-available-height", `${availableHeight}px`);
        };

        if (input.hasAttribute("data-autocomplete-viewport")) {
            window.addEventListener("scroll", updateListHeight, { passive: true });
            window.addEventListener("resize", updateListHeight);
            window.visualViewport?.addEventListener("resize", updateListHeight);
            window.visualViewport?.addEventListener("scroll", updateListHeight);
        }

        const render = () => {
            const query = input.value.trim().toLocaleLowerCase();
            matches = options.filter((option) =>
                option.toLocaleLowerCase().includes(query)
            );
            listbox.replaceChildren();
            matches.forEach((option, index) => {
                const item = document.createElement("div");
                item.className = "custom-autocomplete__option";
                item.id = `${listbox.id}-option-${index}`;
                item.setAttribute("role", "option");
                item.setAttribute("aria-selected", String(option === input.value.trim()));
                item.textContent = option;
                item.addEventListener("mouseenter", () => setActive(index));
                item.addEventListener("mousedown", (event) => event.preventDefault());
                item.addEventListener("click", () => choose(index));
                listbox.append(item);
            });
            activeIndex = -1;
            input.removeAttribute("aria-activedescendant");
            const isOpen = matches.length > 0;
            listbox.hidden = !isOpen;
            input.setAttribute("aria-expanded", String(isOpen));
            updateListHeight();
        };

        const setActive = (index) => {
            activeIndex = index;
            Array.from(listbox.children).forEach((item, itemIndex) => {
                item.classList.toggle("is-active", itemIndex === index);
                item.setAttribute("aria-selected", String(itemIndex === index));
            });
            if (index >= 0) {
                const activeItem = listbox.children[index];
                input.setAttribute("aria-activedescendant", activeItem.id);
                activeItem.scrollIntoView({ block: "nearest" });
            } else {
                input.removeAttribute("aria-activedescendant");
            }
        };

        const choose = (index) => {
            if (index < 0 || index >= matches.length) {
                return;
            }
            input.value = matches[index];
            input.dispatchEvent(new Event("input", { bubbles: true }));
            listbox.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
        };

        input.addEventListener("focus", render);
        input.addEventListener("click", () => {
            if (listbox.hidden) {
                render();
            }
        });
        input.addEventListener("input", render);
        input.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                if (listbox.hidden) {
                    render();
                }
                if (matches.length) {
                    event.preventDefault();
                    const direction = event.key === "ArrowDown" ? 1 : -1;
                    const nextIndex = activeIndex < 0
                        ? (direction > 0 ? 0 : matches.length - 1)
                        : activeIndex + direction;
                    setActive((nextIndex + matches.length) % matches.length);
                }
            } else if (event.key === "Enter" && !listbox.hidden && activeIndex >= 0) {
                event.preventDefault();
                choose(activeIndex);
            } else if (event.key === "Escape" && !listbox.hidden) {
                event.preventDefault();
                listbox.hidden = true;
                input.setAttribute("aria-expanded", "false");
                input.removeAttribute("aria-activedescendant");
            }
        });

        input.addEventListener("blur", () => {
            window.setTimeout(() => {
                listbox.hidden = true;
                input.setAttribute("aria-expanded", "false");
                input.removeAttribute("aria-activedescendant");
            }, 100);
        });
    });
})();
