import { createHints } from "./hints.js";
import { createSourceView } from "./source.js";

export function createResults(api) {
    const title = document.getElementById("result-title");
    const message = document.getElementById("output-message");
    const table = document.getElementById("table-wrap");
    const body = document.querySelector("#result-table tbody");
    const hints = createHints(api.features());
    const source = createSourceView((key) => {
        for (const cell of body.querySelectorAll("[data-source-key]")) {
            cell.closest("tr").classList.toggle("is-pinned", cell.dataset.sourceKey === key);
        }
    });

    function showMessage(text) {
        hints.hide();
        title.textContent = "";
        table.hidden = true;
        body.replaceChildren();
        message.textContent = text;
        message.hidden = !text;
    }

    function showTable(name, data, citations) {
        hints.hide();
        title.textContent = name;
        message.hidden = true;
        body.replaceChildren();

        for (const [group, value] of Object.entries(data)) {
            const isGroup = value !== null && typeof value === "object";
            const entries = isGroup ? Object.entries(value) : [[group, value]];
            entries.forEach(([key, val], index) => {
                const row = document.createElement("tr");
                if (index === 0) {
                    const cell = document.createElement("td");
                    cell.className = "group";
                    cell.rowSpan = entries.length;
                    cell.textContent = isGroup ? group : "";
                    row.appendChild(cell);
                }
                const keyCell = document.createElement("td");
                keyCell.className = "key";
                keyCell.textContent = key;
                hints.attach(keyCell, key);

                const valueCell = document.createElement("td");
                valueCell.textContent = String(val);
                valueCell.classList.toggle("na", val === "не указано");
                if (citations[key]) {
                    valueCell.classList.add("has-source");
                    valueCell.dataset.sourceKey = key;
                    valueCell.addEventListener("mouseenter", () => source.highlight(key));
                    valueCell.addEventListener("mouseleave", () => source.unhighlight());
                    valueCell.addEventListener("click", () => source.pin(key));
                }
                row.append(keyCell, valueCell);
                body.appendChild(row);
            });
        }
        table.scrollTop = 0;
        table.hidden = false;
    }

    return {
        clear() {
            showMessage("");
            source.clear();
        },
        loading() {
            showMessage("Загрузка…");
            source.clear();
        },
        show(name, result, original) {
            source.show(name, original.text, original.citations);
            if (result !== null) {
                showTable(name, result, original.citations || {});
            } else {
                showMessage("Файл ещё не обработан. Нажмите «Обработать».");
            }
        },
    };
}
