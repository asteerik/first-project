(() => {
    const form = document.querySelector("[data-resume-form]");

    if (!form) {
        return;
    }

    form.querySelectorAll("[data-rich-editor]").forEach((editor) => {
        const surface = editor.querySelector("[data-rich-surface]");
        const source = editor.querySelector("[data-rich-source]");
        const counter = editor.querySelector("[data-character-count]");

        const update = () => {
            source.value = surface.innerHTML;
            const length = surface.textContent.trim().length;
            counter.textContent = `${length} символов`;
            surface.style.height = "auto";
            surface.style.height = `${Math.max(surface.scrollHeight, 140)}px`;
        };

        editor.querySelectorAll("[data-command]").forEach((button) => {
            button.addEventListener("click", () => {
                surface.focus();
                if (button.dataset.command === "createLink") {
                    const url = window.prompt("Введите адрес ссылки (https:// или mailto:):");
                    if (url && /^(https?:\/\/|mailto:)\S+$/i.test(url.trim())) {
                        document.execCommand("createLink", false, url.trim());
                    }
                } else {
                    document.execCommand(button.dataset.command, false);
                }
                update();
            });
        });

        surface.addEventListener("input", update);
        surface.addEventListener("paste", (event) => {
            event.preventDefault();
            document.execCommand("insertText", false, event.clipboardData.getData("text/plain"));
            update();
        });

        update();
    });

    form.querySelectorAll("[data-phone-mask='ru']").forEach((input) => {
        const formatPhone = () => {
            let digits = input.value.replace(/\D/g, "");
            if (digits.startsWith("7") || digits.startsWith("8")) {
                digits = digits.slice(1);
            }
            digits = digits.slice(0, 10);
            if (!digits) {
                input.value = input === document.activeElement ? "+7 (" : "";
                return;
            }

            const area = digits.slice(0, 3);
            const first = digits.slice(3, 6);
            const second = digits.slice(6, 8);
            const third = digits.slice(8, 10);
            input.value = `+7 (${area}${digits.length >= 3 ? ")" : ""}${first ? ` ${first}` : ""}${second ? `-${second}` : ""}${third ? `-${third}` : ""}`;
        };

        input.addEventListener("focus", () => {
            if (!input.value) {
                input.value = "+7 (";
            }
        });
        input.addEventListener("input", formatPhone);
        input.addEventListener("blur", () => {
            if (!input.value.replace(/\D/g, "").slice(1)) {
                input.value = "";
            }
        });
        if (input.value) {
            formatPhone();
        }
    });

    form.querySelectorAll("[data-file-drop]").forEach((zone) => {
        const input = zone.querySelector("[data-file-input]");
        const fileName = zone.querySelector("[data-file-name]");
        const originalName = fileName.textContent.trim();

        const showFile = () => {
            const file = input.files[0];
            if (!file) {
                fileName.textContent = originalName;
                input.setCustomValidity("");
                return;
            }
            const validType = /\.(pdf|docx)$/i.test(file.name);
            const validSize = file.size <= 5 * 1024 * 1024;
            input.setCustomValidity(
                validType && validSize ? "" : "Выберите PDF или DOCX размером не более 5 МБ."
            );
            fileName.textContent = file.name;
        };

        input.addEventListener("change", showFile);
        zone.addEventListener("dragover", (event) => {
            event.preventDefault();
            zone.classList.add("is-dragging");
        });
        zone.addEventListener("dragleave", () => zone.classList.remove("is-dragging"));
        zone.addEventListener("drop", (event) => {
            event.preventDefault();
            zone.classList.remove("is-dragging");
            if (event.dataTransfer.files.length) {
                input.files = event.dataTransfer.files;
                showFile();
            }
        });
    });

    form.addEventListener("submit", () => {
        form.querySelectorAll("[data-rich-editor]").forEach((editor) => {
            editor.querySelector("[data-rich-source]").value =
                editor.querySelector("[data-rich-surface]").innerHTML;
        });
    });
})();
