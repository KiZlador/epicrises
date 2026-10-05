(function () {
    const view = document.getElementById("source-view");
    const title = document.getElementById("source-title");

    let text = "";
    let citations = {}; // {признак: {start, end}}
    let pinnedKey = null; // какой признак сейчас закреплён
    function render(range, pinned) {
        if (!range) {
            view.textContent = text;
            return null;
        }
        const start = Math.max(0, Math.min(range.start, text.length));
        const end = Math.max(start, Math.min(range.end, text.length));
        const mark = document.createElement("mark");
        mark.textContent = text.slice(start, end);
        if (pinned) mark.classList.add("pinned");
        view.replaceChildren(
            document.createTextNode(text.slice(0, start)),
            mark,
            document.createTextNode(text.slice(end))
        );
        return mark;
    }

    function scrollToMark(mark) {
        const top = mark.offsetTop;
        const bottom = top + mark.offsetHeight;
        if (top < view.scrollTop + 12 || bottom > view.scrollTop + view.clientHeight - 12) {
            view.scrollTo({
                top: Math.max(0, top - view.clientHeight / 2 + mark.offsetHeight / 2),
                behavior: "smooth",
            });
        }
    }

    window.sourceView = {
        show(name, sourceText, sourceCitations) {
            text = sourceText;
            citations = sourceCitations || {};
            pinnedKey = null;
            title.textContent = "Исходный текст: " + name;
            render(null);
            view.scrollTop = 0;
        },

        clear() {
            text = "";
            citations = {};
            pinnedKey = null;
            title.textContent = "Исходный текст";
            view.textContent = "";
        },

        highlight(key) {
            if (pinnedKey) return; // не перебиваем закреплённую
            const range = citations[key];
            if (!range) return;
            const mark = render(range, false);
            if (mark) scrollToMark(mark);
        },

        unhighlight() {
            if (pinnedKey) return; // закреплённую не трогаем
            render(null);
        },
        pin(key) {
            if (pinnedKey === key) {
                pinnedKey = null;
                render(null);
                document.dispatchEvent(new CustomEvent("source:pinned", { detail: { key: null } }));
                return;
            }
            const range = citations[key];
            if (!range) return;
            pinnedKey = key;
            const mark = render(range, true);
            if (mark) scrollToMark(mark);
            document.dispatchEvent(new CustomEvent("source:pinned", { detail: { key } }));
        },

    };
})();
