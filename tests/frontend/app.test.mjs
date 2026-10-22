import assert from "node:assert/strict";
import test from "node:test";

function element() {
    const children = new Map();
    return {
        hidden: false,
        value: "all",
        listeners: new Map(),
        classList: { toggle() {}, add() {} },
        querySelector(selector) {
            if (!children.has(selector)) children.set(selector, element());
            return children.get(selector);
        },
        querySelectorAll: () => [],
        replaceChildren() {},
        append() {},
        appendChild() {},
        setAttribute() {},
        addEventListener(event, callback) { this.listeners.set(event, callback); },
    };
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

test("failed polling keeps mutations disabled; retry only reads status", async (t) => {
    const page = element();
    const previousDocument = globalThis.document;
    globalThis.document = {
        body: element(),
        getElementById: (id) => page.querySelector(id),
        querySelector: (selector) => page.querySelector(selector),
        createElement: element,
        addEventListener() {},
    };
    t.after(() => { globalThis.document = previousDocument; });
    t.mock.method(globalThis, "setTimeout", (callback) => { queueMicrotask(callback); });

    let offline = false;
    let posts = 0;
    const response = (data) => new Response(JSON.stringify(data));
    t.mock.method(globalThis, "fetch", async (url) => {
        if (String(url).endsWith("features.json")) return response({});
        if (url === "/files") return response({ files: [{ name: "new.md", processed: posts > 0 }] });
        if (url === "/process") {
            posts++;
            offline = true;
            return response({ status: "queued", total: 1, completed: 0 });
        }
        if (url === "/process/status") {
            if (offline) throw new TypeError("Connection lost");
            return response(posts === 0 ? { status: "idle" } : { status: "done", total: 1, succeeded: 1 });
        }
        assert.fail(`Unexpected request: ${url}`);
    });

    await import("../../frontend/static/app.js");
    await settle();
    const processButton = page.querySelector("process-btn");
    const uploadButton = page.querySelector("upload-btn");
    const retry = page.querySelector("sync-btn");
    assert.equal(processButton.disabled, false);

    await processButton.listeners.get("click")();
    assert.equal(processButton.disabled, true);
    assert.equal(uploadButton.disabled, true);
    assert.equal(retry.hidden, false);
    assert.equal(posts, 1);

    offline = false;
    retry.listeners.get("click")();
    await settle();
    assert.equal(retry.hidden, true);
    assert.equal(uploadButton.disabled, false);
    assert.equal(processButton.disabled, true);
    assert.equal(posts, 1, "Recovery must not repeat the processing POST");
});
