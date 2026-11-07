document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector(".catalog-filters");
    const remoteCheckbox = document.getElementById("catalog-remote");
    const remoteFilter = remoteCheckbox && remoteCheckbox.closest(".catalog-remote-filter");

    if (!form || !remoteCheckbox || !remoteFilter) return;

    function updateRemoteFilter() {
        remoteFilter.classList.toggle("is-enabled", remoteCheckbox.checked);

        const remoteOffInput = form.querySelector("[data-remote-off]");
        if (remoteCheckbox.checked) {
            if (remoteOffInput) remoteOffInput.remove();
        } else if (!remoteOffInput) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = "remote";
            input.value = "0";
            input.dataset.remoteOff = "";
            form.appendChild(input);
        }

        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    remoteCheckbox.addEventListener("change", updateRemoteFilter);
});
