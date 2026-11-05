(() => {
    const format = (value) => {
        const digits = value.replace(/\D/g, "");
        return digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    };

    document.querySelectorAll("[data-grouped-number]").forEach((input) => {
        input.addEventListener("input", () => {
            const start = input.selectionStart;
            const digitsBeforeCaret = input.value.slice(0, start).replace(/\D/g, "").length;
            input.value = format(input.value);

            let caret = 0;
            let digitsSeen = 0;
            while (caret < input.value.length && digitsSeen < digitsBeforeCaret) {
                if (/\d/.test(input.value[caret])) {
                    digitsSeen += 1;
                }
                caret += 1;
            }
            input.setSelectionRange(caret, caret);
        });

        input.value = format(input.value);
    });
})();
