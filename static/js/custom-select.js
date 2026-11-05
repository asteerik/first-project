(() => {
    const selects = document.querySelectorAll("select.js-custom-select:not([multiple])");
    let generatedId = 0;

    selects.forEach((select) => {
        const options = Array.from(select.options);
        if (!options.length) {
            return;
        }
        generatedId += 1;

        const wrapper = document.createElement("div");
        wrapper.className = "custom-select";

        const trigger = document.createElement("button");
        trigger.className = "custom-select__trigger";
        trigger.type = "button";
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");

        const label = select.labels && select.labels[0];
        if (label) {
            if (!label.id) {
                label.id = `custom-select-label-${generatedId}`;
            }
            trigger.setAttribute("aria-labelledby", label.id);
        } else if (select.getAttribute("aria-label")) {
            trigger.setAttribute("aria-label", select.getAttribute("aria-label"));
        }

        const value = document.createElement("span");
        value.className = "custom-select__value";
        const arrow = document.createElement("span");
        arrow.className = "custom-select__arrow";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "⌄";
        trigger.append(value, arrow);

        const listbox = document.createElement("div");
        listbox.className = "custom-select__listbox";
        listbox.id = `custom-select-listbox-${generatedId}`;
        listbox.setAttribute("role", "listbox");
        trigger.setAttribute("aria-controls", listbox.id);

        const optionElements = options.map((option, index) => {
            const optionElement = document.createElement("div");
            optionElement.className = "custom-select__option";
            optionElement.id = `${listbox.id}-option-${index}`;
            optionElement.dataset.index = String(index);
            optionElement.setAttribute("role", "option");
            optionElement.setAttribute("aria-selected", "false");
            optionElement.textContent = option.textContent.trim();
            if (option.disabled) {
                optionElement.setAttribute("aria-disabled", "true");
            }
            listbox.append(optionElement);
            return optionElement;
        });

        select.classList.add("custom-select__native");
        select.setAttribute("aria-hidden", "true");
        select.tabIndex = -1;
        select.insertAdjacentElement("afterend", wrapper);
        wrapper.append(trigger, listbox);

        let activeIndex = -1;
        let typeahead = "";
        let typeaheadTimer;

        const enabledIndex = (start, direction) => {
            let index = start;
            while (index >= 0 && index < options.length) {
                if (!options[index].disabled) {
                    return index;
                }
                index += direction;
            }
            return -1;
        };

        const syncValue = () => {
            value.textContent = options[select.selectedIndex].textContent.trim();
            optionElements.forEach((optionElement, index) => {
                optionElement.setAttribute(
                    "aria-selected",
                    String(index === select.selectedIndex)
                );
            });
        };

        const setActive = (index) => {
            activeIndex = index;
            optionElements.forEach((optionElement) => {
                optionElement.classList.remove("is-active");
            });
            if (activeIndex >= 0) {
                const activeOption = optionElements[activeIndex];
                activeOption.classList.add("is-active");
                trigger.setAttribute("aria-activedescendant", activeOption.id);
                activeOption.scrollIntoView({ block: "nearest" });
            } else {
                trigger.removeAttribute("aria-activedescendant");
            }
        };

        const close = (returnFocus = false) => {
            listbox.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
            trigger.removeAttribute("aria-activedescendant");
            activeIndex = -1;
            optionElements.forEach((optionElement) => {
                optionElement.classList.remove("is-active");
            });
            if (returnFocus) {
                trigger.focus();
            }
        };

        const open = (index = select.selectedIndex, direction = 1) => {
            listbox.hidden = false;
            trigger.setAttribute("aria-expanded", "true");
            setActive(enabledIndex(index, direction));
        };

        const choose = (index) => {
            if (index < 0 || options[index].disabled) {
                return;
            }
            select.selectedIndex = index;
            syncValue();
            select.dispatchEvent(new Event("change", { bubbles: true }));
            close(true);
        };

        trigger.addEventListener("click", () => {
            if (listbox.hidden) {
                open();
            } else {
                close();
            }
        });

        trigger.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                const direction = event.key === "ArrowDown" ? 1 : -1;
                if (listbox.hidden) {
                    open(select.selectedIndex + direction, direction);
                } else {
                    setActive(enabledIndex(activeIndex + direction, direction));
                }
            } else if (event.key === "Home" || event.key === "End") {
                event.preventDefault();
                if (listbox.hidden) {
                    open(
                        event.key === "Home" ? 0 : options.length - 1,
                        event.key === "Home" ? 1 : -1
                    );
                } else {
                    setActive(
                        enabledIndex(
                            event.key === "Home" ? 0 : options.length - 1,
                            event.key === "Home" ? 1 : -1
                        )
                    );
                }
            } else if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                if (listbox.hidden) {
                    open();
                } else {
                    choose(activeIndex);
                }
            } else if (event.key === "Escape" && !listbox.hidden) {
                event.preventDefault();
                close();
            } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
                typeahead += event.key.toLocaleLowerCase();
                window.clearTimeout(typeaheadTimer);
                typeaheadTimer = window.setTimeout(() => {
                    typeahead = "";
                }, 500);
                const match = options.findIndex(
                    (option, index) =>
                        !option.disabled &&
                        index !== select.selectedIndex &&
                        option.textContent.trim().toLocaleLowerCase().startsWith(typeahead)
                );
                if (match >= 0) {
                    if (listbox.hidden) {
                        open(match);
                    } else {
                        setActive(match);
                    }
                }
            }
        });

        optionElements.forEach((optionElement, index) => {
            optionElement.addEventListener("mouseenter", () => {
                if (!options[index].disabled) {
                    setActive(index);
                }
            });
            optionElement.addEventListener("mousedown", (event) => event.preventDefault());
            optionElement.addEventListener("click", () => choose(index));
        });

        select.addEventListener("change", syncValue);
        document.addEventListener("click", (event) => {
            if (!wrapper.contains(event.target)) {
                close();
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Tab") {
                close();
            }
        });

        syncValue();
        listbox.hidden = true;
    });
})();
