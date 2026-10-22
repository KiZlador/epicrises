import { createApi } from "./api.js";
import { createFiles } from "./files.js";
import { createResults } from "./results.js";
import { createSave } from "./save.js";
import { createUpload } from "./upload.js";
import { jobIsActive, jobMessage, watchJob } from "./jobs.js";

const api = createApi();
const status = document.getElementById("process-status");
const retry = document.getElementById("sync-btn");
const save = createSave(api);
const results = createResults(api);
const upload = createUpload({
    upload: (incoming) => files.mutate(() => api.upload(incoming)),
    onError: mutationError,
});
const files = createFiles({
    api,
    results,
    onError: showError,
    onMutationError: mutationError,
    onState(state) {
        save.update(state);
        upload.setBusy(state.busy);
    },
});

function report(text) {
    status.textContent = text;
    status.hidden = !text;
}

function showError(error) {
    report(error.message || "Не удалось связаться с сервером");
}

function mutationError(error) {
    showError(error);
    synchronize();
}

async function followJob(job) {
    const completed = await watchJob(job, { getStatus: api.jobStatus, report });
    await files.refresh();
    if (completed.first) await files.select(completed.first).catch(showError);
}

async function synchronize(selectInitial = false) {
    files.setBusy(true, "Проверка…");
    retry.hidden = true;
    try {
        const job = await api.jobStatus();
        if (jobIsActive(job)) {
            files.setBusy(true);
            await followJob(job);
        } else {
            await files.refresh();
            if (job.status !== "idle") report(jobMessage(job));
            if (job.first) await files.select(job.first).catch(showError);
            else if (selectInitial) await files.selectFirstProcessed().catch(showError);
        }
        files.setBusy(false);
    } catch (error) {
        report(`${error.message}\nНе удалось проверить состояние. Повторите проверку перед изменением файлов.`);
        retry.hidden = false;
    }
}

document.getElementById("process-btn").addEventListener("click", async () => {
    if (!files.state().canProcess) return;
    files.setBusy(true);
    try {
        await followJob(await api.startJob());
        files.setBusy(false);
    } catch (error) {
        showError(error);
        await synchronize();
    }
});
retry.addEventListener("click", () => {
    report("");
    synchronize();
});

synchronize(true);
