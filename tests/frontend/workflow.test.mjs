import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, createApi } from "../../frontend/static/api.js";
import { jobMessage, watchJob } from "../../frontend/static/jobs.js";
import { downloadName } from "../../frontend/static/save.js";
import { fileState } from "../../frontend/static/state.js";

const json = (data, status = 200) => new Response(JSON.stringify(data), { status });

test("processed documents stay exportable but cannot start another batch", () => {
    const files = [{ name: "old.md", processed: true }];
    const state = fileState(files, "old.md", false);
    assert.equal(state.canProcess, false);
    assert.equal(state.canClear, true);
    assert.equal(state.selectedProcessed, true);
    assert.equal(state.processedCount, 1);
    assert.equal(state.pendingCount, 0);
});

test("adding new documents enables processing only until they are complete", () => {
    const files = [
        { name: "old.md", processed: true },
        { name: "new.md", processed: false },
    ];
    assert.equal(fileState(files, "old.md", false).canProcess, true);
    assert.equal(fileState(files, "new.md", false).selectedProcessed, false);
    assert.equal(fileState(files, "new.md", true).canProcess, false);
    files[1].processed = true;
    assert.equal(fileState(files, "new.md", false).canProcess, false);
    assert.equal(fileState([], null, false).canProcess, false);
});

test("an unprocessed document still displays its original text", async () => {
    const name = "Эпикриз №1.md";
    const requests = [];
    const api = createApi(async (url) => {
        requests.push(url);
        return url.startsWith("/result/")
            ? json({ error: "Нет результата" }, 404)
            : json({ text: "Исходный текст", citations: {} });
    });
    const document = await api.document(name);
    assert.equal(document.result, null);
    assert.equal(document.source.text, "Исходный текст");
    assert.deepEqual(requests, ["/result/", "/source/"].map((prefix) => prefix + encodeURIComponent(name)));
});

test("missing source and broken result requests are reported, not hidden as pending", async () => {
    const missingSource = createApi(async () => json({ error: "Файл удалён" }, 404));
    await assert.rejects(missingSource.document("removed.md"), { status: 404, message: "Файл удалён" });

    const brokenResult = createApi(async (url) => url.startsWith("/result/")
        ? json({ error: "Не удалось прочитать результат" }, 500)
        : json({ text: "text", citations: {} }));
    await assert.rejects(brokenResult.document("broken.md"), { status: 500 });
});

test("HTTP and network failures remain readable even without a JSON response", async () => {
    const unavailable = createApi(async () => new Response("Proxy unavailable", { status: 502 }));
    await assert.rejects(unavailable.listFiles(), { message: "Ошибка запроса (502)", status: 502 });

    const offline = createApi(async () => { throw new TypeError("Failed to fetch"); });
    await assert.rejects(offline.startJob(), (error) => error instanceof ApiError && error.status === 0);
});

test("a server no-op does not poll or show a fake completed batch", async () => {
    const reports = [];
    const job = { status: "done", total: 0, completed: 0, succeeded: 0, skipped: 5 };
    const result = await watchJob(job, {
        getStatus: () => assert.fail("A completed no-op must not be polled"),
        wait: () => assert.fail("A completed no-op must not wait"),
        report: (text) => reports.push(text),
    });
    assert.equal(result, job);
    assert.deepEqual(reports, ["Новых файлов для обработки нет."]);
});

test("polling follows the current job and retains partial failure details", async () => {
    const statuses = [
        { status: "running", total: 2, completed: 1, current: "new.md" },
        {
            status: "done", total: 2, completed: 2, succeeded: 1, skipped: 3,
            first: "new.md", errors: [{ file: "broken.md", error: "Некорректный документ" }],
            warnings: [{ file: "new.md", messages: ["Проверить дату"] }],
        },
    ];
    const reports = [];
    const waits = [];
    const result = await watchJob({ status: "queued", total: 2, completed: 0 }, {
        getStatus: async () => statuses.shift(),
        wait: async (milliseconds) => waits.push(milliseconds),
        report: (text) => reports.push(text),
    });
    assert.deepEqual(waits, [1000, 1000]);
    assert.equal(result.first, "new.md");
    assert.equal(statuses.length, 0);
    assert.match(reports.at(-1), /Готово: 1\/2/);
    assert.match(reports.at(-1), /Уже обработано: 3/);
    assert.match(reports.at(-1), /broken.md: Некорректный документ/);
    assert.match(reports.at(-1), /new.md: Проверить дату/);
});

test("failed jobs and unavailable LLM mode remain visible", () => {
    assert.match(jobMessage({ status: "failed", error: "Модель недоступна" }), /Модель недоступна/);
    assert.match(jobMessage({ status: "running", total: 1, completed: 0, mode: "regex-statistics" }), /LLM отключена/);
});

test("export filenames distinguish individual JSON and batch ZIP", () => {
    assert.equal(downloadName({ scope: "one", format: "json", name: "Эпикриз.MD" }), "Эпикриз.json");
    assert.equal(downloadName({ scope: "all", format: "json" }), "results.zip");
    assert.equal(downloadName({ scope: "all", format: "xlsx" }), "results.xlsx");
});


test("unreadable successful responses and JSON-null errors have useful messages", async () => {
    const malformed = createApi(async () => new Response("truncated", { status: 200 }));
    await assert.rejects(malformed.listFiles(), { message: "Не удалось прочитать ответ сервера", status: 200 });
    const emptyError = createApi(async () => json(null, 500));
    await assert.rejects(emptyError.listFiles(), { message: "Ошибка запроса (500)", status: 500 });
});

test("a polling failure propagates without resubmitting processing", async () => {
    let reads = 0;
    await assert.rejects(watchJob({ status: "running", completed: 0, total: 1 }, {
        getStatus: async () => { reads++; throw new ApiError("offline", 0); },
        wait: async () => {},
        report: () => {},
    }), { status: 0 });
    assert.equal(reads, 1);
});
