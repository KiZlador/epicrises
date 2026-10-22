export function createSave(api) {
    const bar = document.getElementById("save-bar");
    const scope = document.getElementById("save-scope");
    const format = document.getElementById("save-format");
    const button = document.getElementById("save-btn");
    const message = document.getElementById("save-message");
    const oneOption = scope.querySelector('option[value="one"]');
    const jsonOption = format.querySelector('option[value="json"]');
    let state = { selected: null, selectedProcessed: false, processedCount: 0 };
    let downloading = false;

    function updateFormatLabel() {
        jsonOption.textContent = scope.value === "all"
            ? "JSON (отдельные файлы в архиве .zip)"
            : "JSON (.json)";
    }
    scope.addEventListener("change", updateFormatLabel);

    function update(next) {
        const previous = state.selected;
        state = next;
        bar.hidden = state.processedCount === 0;
        button.disabled = downloading || state.processedCount === 0;
        oneOption.disabled = !state.selectedProcessed;
        oneOption.textContent = state.selectedProcessed
            ? `Выбранный файл: ${state.selected}`
            : "Выбранный файл";

        if (!state.selectedProcessed) {
            scope.value = "all";
        } else if (state.selected !== previous) {
            scope.value = "one";
        }
        updateFormatLabel();
    }

    button.addEventListener("click", async () => {
        if (downloading || !state.processedCount) return;
        if (scope.value === "one" && !state.selectedProcessed) return;
        const params = { scope: scope.value, format: format.value };
        if (params.scope === "one") params.name = state.selected;
        downloading = true;
        update(state);
        message.textContent = "";
        try {
            saveBlob(await api.download(params), downloadName(params));
        } catch (error) {
            message.textContent = error.message;
        } finally {
            downloading = false;
            update(state);
        }
    });

    return { update };
}

export function downloadName({ scope, format, name }) {
    const basename = scope === "one" ? name.replace(/\.md$/i, "") : "results";
    const extension = scope === "all" && format === "json" ? "zip" : format;
    return `${basename}.${extension}`;
}

function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
