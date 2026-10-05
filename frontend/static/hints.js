(function () {
    let hints = {};
    const ready = fetch("/static/features.json")
        .then((r) => (r.ok ? r.json() : {}))
        .then((data) => { hints = data; })
        .catch(() => {});

    const tip = document.createElement("div");
    tip.id = "hint-tooltip";
    tip.hidden = true;
    document.body.appendChild(tip);

    function show(key, event) {
        const hint = hints[key];
        if (!hint) return;

        const title = document.createElement("div");
        title.className = "hint-key";
        title.textContent = key;
        const meaning = document.createElement("div");
        meaning.textContent = hint.meaning;
        const example = document.createElement("div");
        example.className = "hint-example";
        example.textContent = hint.example;
        tip.replaceChildren(title, meaning, example);

        tip.hidden = false;
        move(event);
    }

    function move(event) {
        const gap = 14;
        let x = event.clientX + gap;
        let y = event.clientY + gap;
        if (x + tip.offsetWidth > window.innerWidth - 8) x = event.clientX - tip.offsetWidth - gap;
        if (y + tip.offsetHeight > window.innerHeight - 8) y = event.clientY - tip.offsetHeight - gap;
        tip.style.left = Math.max(8, x) + "px";
        tip.style.top = Math.max(8, y) + "px";
    }

    function hide() { tip.hidden = true; }
    window.attachHint = function (element, key) {
        ready.then(() => {
            if (!hints[key]) return;
            element.classList.add("has-hint");
            element.addEventListener("mouseenter", (e) => show(key, e));
            element.addEventListener("mousemove", (e) => { if (!tip.hidden) move(e); });
            element.addEventListener("mouseleave", hide);
        });
    };
    window.hideHint = hide;
    document.addEventListener("scroll", hide, true);
})();
