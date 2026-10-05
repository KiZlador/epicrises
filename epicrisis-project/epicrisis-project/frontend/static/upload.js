(function () {
    const button = document.getElementById("upload-btn");
    const input = document.getElementById("file-input");
    const message = document.getElementById("upload-message");

    button.addEventListener("click", () => input.click());

    input.addEventListener("change", async () => {
        if (!input.files.length) return;

        const formData = new FormData();
        for (const file of input.files) {
            formData.append("files", file);
        }

        button.disabled = true;
        message.textContent = "Загрузка...";

        try {
            const response = await fetch("/upload", { method: "POST", body: formData });
            const data = await response.json();

            const skipped = data.skipped && data.skipped.length
                ? "Пропущено: " + data.skipped.join(", ")
                : "";
            message.textContent = response.ok ? skipped : (data.error || "Ошибка загрузки") +
                (skipped ? ". " + skipped : "");
            document.dispatchEvent(new Event("files:changed"));
        } catch (err) {
            message.textContent = "Не удалось связаться с сервером";
        } finally {
            button.disabled = false;
            input.value = ""; // позволяет выбрать те же файлы повторно
        }
    });
})();
