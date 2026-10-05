(function () {
    const list = document.getElementById("file-list");
    const counter = document.getElementById("upload-status");
    const clearBtn = document.getElementById("clear-btn");
    const processBtn = document.getElementById("process-btn");
    const title = document.getElementById("result-title");
    const message = document.getElementById("output-message");
    const tableWrap = document.getElementById("table-wrap");
    const tbody = document.querySelector("#result-table tbody");
    const status = document.getElementById("process-status");
    let busy = false;

    let files = [];      // [{name, processed}]
    let selected = null; // имя выбранного файла
    function showMessage(text) {
        window.hideHint && window.hideHint();
        title.textContent = "";
        tableWrap.hidden = true;
        message.textContent = text;
        message.hidden = !text;
    }

    function showTable(name, data, citations) {
        window.hideHint && window.hideHint();
        title.textContent = name;
        message.hidden = true;
        tbody.innerHTML = "";

        for (const [group, value] of Object.entries(data)) {
            const isGroup = value !== null && typeof value === "object";
            const entries = isGroup ? Object.entries(value) : [[group, value]];

            entries.forEach(([key, val], i) => {
                const tr = document.createElement("tr");
                if (i === 0) {
                    const groupCell = document.createElement("td");
                    groupCell.className = "group";
                    groupCell.rowSpan = entries.length;
                    groupCell.textContent = isGroup ? group : "";
                    tr.appendChild(groupCell);
                }
                const keyCell = document.createElement("td");
                keyCell.className = "key";
                keyCell.textContent = key;
                window.attachHint && window.attachHint(keyCell, key); // подсказка с описанием
                const valueCell = document.createElement("td");
                valueCell.textContent = String(val);
                valueCell.classList.toggle("na", val === "не указано");
                if (citations && citations[key]) {
                    valueCell.classList.add("has-source");
                    valueCell.addEventListener("mouseenter", () => sourceView.highlight(key));
                    valueCell.addEventListener("mouseleave", () => sourceView.unhighlight());
                    valueCell.addEventListener("click", () => {
                        sourceView.pin(key);
                    });
                    valueCell.dataset.sourceKey = key;
                }
                tr.append(keyCell, valueCell);
                tbody.appendChild(tr);
            });
        }
        tableWrap.scrollTop = 0;
        tableWrap.hidden = false;
    }

    document.addEventListener("source:pinned", (event) => {
        for (const cell of tbody.querySelectorAll("[data-source-key]")) {
            cell.closest("tr").classList.toggle("is-pinned", cell.dataset.sourceKey === event.detail.key);
        }
    });

    function report(text) {
        status.textContent = text;
        status.hidden = !text;
    }

    function showError(error) {
        report(error.message || "Не удалось связаться с сервером");
    }

    async function request(url, options) {
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Ошибка запроса");
        return data;
    }

    function clearOutput() {
        showMessage("");
        sourceView.clear();
    }
    async function loadFiles() {
        files = (await request("/files")).files;
        if (selected && !files.some((f) => f.name === selected)) {
            selected = null;
            clearOutput();
        }
        render();
    }

    function render() {
        counter.textContent = files.length ? `Загружено файлов: ${files.length}` : "";
        clearBtn.disabled = processBtn.disabled = busy || files.length === 0;
        processBtn.textContent = busy ? "Обработка…" : "Обработать";

        list.innerHTML = "";
        for (const file of files) {
            const li = document.createElement("li");
            li.classList.toggle("selected", file.name === selected);
            li.classList.toggle("processed", file.processed);

            const name = document.createElement("span");
            name.className = "name";
            name.textContent = file.name;
            name.addEventListener("click", () => select(file.name).catch(showError));

            const remove = document.createElement("button");
            remove.className = "remove";
            remove.type = "button";
            remove.title = "Удалить файл";
            remove.textContent = "×";
            remove.disabled = busy;
            remove.addEventListener("click", () => removeFile(file.name).catch(showError));

            li.append(name, remove);
            list.appendChild(li);
        }
        document.dispatchEvent(new CustomEvent("files:state", {
            detail: {
                selected,
                selectedProcessed: files.some((f) => f.name === selected && f.processed),
                processedCount: files.filter((f) => f.processed).length,
            },
        }));
    }

    async function select(name) {
        selected = name;
        render();
        const encoded = encodeURIComponent(name);
        const [resultResponse, sourceResponse] = await Promise.all([
            fetch("/result/" + encoded),
            fetch("/source/" + encoded),
        ]);
        if (!resultResponse.ok && resultResponse.status !== 404) {
            const error = await resultResponse.json();
            throw new Error(error.error || "Не удалось загрузить результат");
        }
        if (!sourceResponse.ok) {
            const error = await sourceResponse.json();
            throw new Error(error.error || "Не удалось загрузить исходный текст");
        }
        const result = resultResponse.ok ? await resultResponse.json() : null;
        const source = await sourceResponse.json();
        if (selected !== name) return; // пользователь уже выбрал другой файл

        if (source) {
            sourceView.show(name, source.text, source.citations);
        } else {
            sourceView.clear();
        }
        if (result) {
            showTable(name, result, source ? source.citations : {});
        } else {
            showMessage("Файл ещё не обработан. Нажмите «Обработать».");
        }
    }

    async function removeFile(name) {
        await request("/files/" + encodeURIComponent(name), { method: "DELETE" });
        await loadFiles();
    }

    clearBtn.addEventListener("click", async () => {
        if (!confirm("Удалить все загруженные файлы?")) return;
        try {
            await request("/files", { method: "DELETE" });
            selected = null;
            clearOutput();
            await loadFiles();
        } catch (error) { showError(error); }
    });

    async function watchJob(job) {
        busy = true;
        render();
        try {
            while (["queued", "running"].includes(job.status)) {
                report(`${job.status === "queued" ? "В очереди" : "Обработка"}: ${job.completed}/${job.total}` +
                    (job.current ? ` · ${job.current}` : "") +
                    (job.mode === "regex-statistics" ? " · LLM отключена" : ""));
                await new Promise(resolve => setTimeout(resolve, 1000));
                job = await request("/process/status");
            }
            await loadFiles();
            if (job.first) await select(job.first);
            report([
                job.status === "failed" ? job.error : `Готово: ${job.succeeded}/${job.total}`,
                job.mode === "regex-statistics" ? "LLM отключена: результаты получены правилами." : "",
                ...(job.errors || []).map(item => `${item.file}: ${item.error}`),
                ...(job.warnings || []).map(item => `${item.file}: ${item.messages.join("; ")}`),
            ].filter(Boolean).join("\n"));
        } finally {
            busy = false;
            render();
        }
    }

    processBtn.addEventListener("click", async () => {
        busy = true;
        render();
        try { await watchJob(await request("/process", {method: "POST"})); }
        catch (error) { showError(error); }
        finally { busy = false; render(); }
    });

    document.addEventListener("files:changed", () => loadFiles().catch(showError));
    loadFiles().then(async () => {
        const job = await request("/process/status");
        if (["queued", "running"].includes(job.status)) {
            await watchJob(job);
            return;
        }
        const first = files.find((f) => f.processed);
        if (first) await select(first.name);
    }).catch(showError);
})();
