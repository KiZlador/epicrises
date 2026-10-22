import { fileState } from "./state.js";

export function createFiles({ api, results, onState, onError, onMutationError }) {
    const list = document.getElementById("file-list");
    const counter = document.getElementById("upload-status");
    const clearButton = document.getElementById("clear-btn");
    const processButton = document.getElementById("process-btn");
    const processLabel = document.getElementById("process-label");
    let files = [];
    let selected = null;
    let busy = true;
    let busyLabel = "Проверка…";
    let selectionVersion = 0;
    let refreshVersion = 0;

    function state() {
        return fileState(files, selected, busy);
    }

    function render() {
        const current = state();
        counter.textContent = files.length ? `Загружено файлов: ${files.length}` : "";
        clearButton.disabled = !current.canClear;
        processButton.disabled = !current.canProcess;
        processLabel.textContent = busy ? busyLabel : "Обработать";

        list.replaceChildren();
        for (const file of files) {
            const item = document.createElement("li");
            item.classList.toggle("selected", file.name === selected);
            item.classList.toggle("processed", file.processed);

            const name = document.createElement("button");
            name.className = "name";
            name.type = "button";
            name.textContent = file.name;
            name.addEventListener("click", () => select(file.name).catch(onError));

            const remove = document.createElement("button");
            remove.className = "remove";
            remove.type = "button";
            remove.title = "Удалить файл";
            remove.setAttribute("aria-label", `Удалить ${file.name}`);
            remove.textContent = "×";
            remove.disabled = busy;
            remove.addEventListener("click", () => removeFile(file.name).catch(onMutationError));

            item.append(name, remove);
            list.appendChild(item);
        }
        onState(current);
    }

    async function refresh() {
        const version = ++refreshVersion;
        const updated = await api.listFiles();
        if (version !== refreshVersion) return;
        files = updated;
        if (selected && !files.some((file) => file.name === selected)) {
            selected = null;
            selectionVersion++;
            results.clear();
        }
        render();
    }

    async function select(name) {
        const version = ++selectionVersion;
        selected = name;
        render();
        results.loading();
        try {
            const data = await api.document(name);
            if (version === selectionVersion) results.show(name, data.result, data.source);
        } catch (error) {
            if (version === selectionVersion) {
                results.clear();
                throw error;
            }
        }
    }

    async function removeFile(name) {
        if (busy) return;
        await mutate(() => api.deleteFile(name));
    }

    clearButton.addEventListener("click", async () => {
        if (busy || !confirm("Удалить все загруженные файлы?")) return;
        try {
            await mutate(api.clearFiles);
        } catch (error) {
            onMutationError(error);
        }
    });

    function setBusy(value, label = "Обработка…") {
        busy = value;
        busyLabel = label;
        render();
    }

    async function mutate(action) {
        if (busy) throw new Error("Дождитесь завершения текущей операции");
        setBusy(true, "Обновление…");
        try {
            const result = await action();
            await refresh();
            return result;
        } finally {
            setBusy(false);
        }
    }

    return {
        refresh,
        select,
        state,
        mutate,
        setBusy,
        async selectFirstProcessed() {
            const first = files.find((file) => file.processed);
            if (first) await select(first.name);
        },
    };
}
