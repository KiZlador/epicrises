export function jobIsActive(job) {
    return ["queued", "running"].includes(job.status);
}

export function jobMessage(job) {
    if (jobIsActive(job)) {
        return `${job.status === "queued" ? "В очереди" : "Обработка"}: ${job.completed}/${job.total}` +
            (job.current ? ` · ${job.current}` : "") +
            (job.mode === "regex-statistics" ? " · LLM отключена" : "");
    }
    if (job.status === "idle") return "Нет активной обработки.";
    if (job.status === "done" && job.total === 0) return "Новых файлов для обработки нет.";

    return [
        job.status === "failed" ? job.error : `Готово: ${job.succeeded}/${job.total}`,
        job.skipped ? `Уже обработано: ${job.skipped}` : "",
        job.mode === "regex-statistics" ? "LLM отключена: результаты получены правилами." : "",
        ...(job.errors || []).map((item) => `${item.file}: ${item.error}`),
        ...(job.warnings || []).map((item) => `${item.file}: ${item.messages.join("; ")}`),
    ].filter(Boolean).join("\n");
}

export async function watchJob(job, { getStatus, report, wait = delay }) {
    report(jobMessage(job));
    while (jobIsActive(job)) {
        await wait(1000);
        job = await getStatus();
        report(jobMessage(job));
    }
    return job;
}

function delay(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
