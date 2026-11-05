(() => {
    const dialog = document.querySelector("[data-application-dialog]");
    if (!dialog) {
        return;
    }

    const trigger = document.querySelector("[data-open-application-dialog]");
    const closeButton = dialog.querySelector("[data-close-application-dialog]");

    trigger?.addEventListener("click", () => dialog.showModal());
    closeButton?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });
    dialog.addEventListener("close", () => trigger?.focus());

    if (dialog.hasAttribute("data-open-on-load")) {
        dialog.showModal();
    }
})();
