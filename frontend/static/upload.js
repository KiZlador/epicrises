export function createUpload({ upload, onError }) {
    const button = document.getElementById("upload-btn");
    const input = document.getElementById("file-input");
    const message = document.getElementById("upload-message");
    let processing = true;
    let uploading = false;

    function render() {
        button.disabled = processing || uploading;
    }

    button.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
        if (!input.files.length || processing || uploading) return;
        uploading = true;
        render();
        message.textContent = "Загрузка…";
        try {
            const data = await upload(input.files);
            message.textContent = skippedMessage(data.skipped);
        } catch (error) {
            message.textContent = [error.message, skippedMessage(error.data?.skipped)].filter(Boolean).join(". ");
            onError(error);
        } finally {
            uploading = false;
            input.value = "";
            render();
        }
    });

    render();
    return {
        setBusy(value) {
            processing = value;
            render();
        },
    };
}

function skippedMessage(names) {
    return names?.length ? "Пропущено: " + names.join(", ") : "";
}
