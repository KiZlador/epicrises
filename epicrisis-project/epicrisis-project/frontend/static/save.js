(function () {
    const bar = document.getElementById("save-bar");
    const scope = document.getElementById("save-scope");
    const format = document.getElementById("save-format");
    const button = document.getElementById("save-btn");
    const message = document.getElementById("save-message");
    const oneOption = scope.querySelector('option[value="one"]');
    const jsonOption = format.querySelector('option[value="json"]');

    let state = { selected: null, selectedProcessed: false, processedCount: 0 };

    function updateFormatLabel() {
        jsonOption.textContent = scope.value === "all"
            ? "JSON (отдельные файлы в архиве .zip)"
            : "JSON (.json)";
    }
    scope.addEventListener("change", updateFormatLabel);

    document.addEventListener("files:state", (event) => {
        const previous = state.selected;
        state = event.detail;

        bar.hidden = state.processedCount === 0;
        oneOption.disabled = !state.selectedProcessed;
        oneOption.textContent = state.selectedProcessed
            ? `Выбранный файл: ${state.selected}`
            : "Выбранный файл";

        if (!state.selectedProcessed) {
            scope.value = "all";
        } else if (state.selected !== previous) {
            scope.value = "one"; // выбрали другой файл — по умолчанию сохраняем его
        }
        updateFormatLabel();
    });

    button.addEventListener("click", async () => {
        const params = new URLSearchParams({ scope: scope.value, format: format.value });
        let filename = "results";
        if (scope.value === "one") {
            params.set("name", state.selected);
            filename = state.selected.replace(/\.md$/i, "");
        }
        const zipped = scope.value === "all" && format.value === "json";
        filename += "." + (zipped ? "zip" : format.value);

        button.disabled = true;
        message.textContent = "";
        try {
            const response = await fetch("/download?" + params);
            if (!response.ok) {
                const data = await response.json();
                message.textContent = data.error || "Не удалось сохранить";
                return;
            }
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement("a");
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) {
            message.textContent = "Не удалось связаться с сервером";
        } finally {
            button.disabled = false;
        }
    });
})();
