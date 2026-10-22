import assert from "node:assert/strict";
import test from "node:test";

import { createFiles } from "../../frontend/static/files.js";

function deferred() {
    let resolve;
    const promise = new Promise((done) => { resolve = done; });
    return { promise, resolve };
}

function setup(t, api, results = {}) {
    function element() {
        return {
            classList: { toggle() {} },
            replaceChildren() {},
            append() {},
            appendChild() {},
            addEventListener() {},
            setAttribute() {},
        };
    }
    const nodes = new Map();
    const previous = globalThis.document;
    globalThis.document = {
        getElementById(id) {
            if (!nodes.has(id)) nodes.set(id, element());
            return nodes.get(id);
        },
        createElement: element,
    };
    t.after(() => { globalThis.document = previous; });
    const controller = createFiles({
        api,
        results: { loading() {}, clear() {}, show() {}, ...results },
        onState() {},
        onError: assert.fail,
        onMutationError: assert.fail,
    });
    return { controller, nodes };
}

test("upload/delete locks processing until the refreshed list arrives", async (t) => {
    const update = deferred();
    const uploaded = deferred();
    const { controller, nodes } = setup(t, {
        listFiles: () => update.promise,
    });
    controller.setBusy(false);
    const mutation = controller.mutate(() => uploaded.promise);
    assert.equal(controller.state().busy, true);
    assert.equal(nodes.get("process-btn").disabled, true);
    await assert.rejects(controller.mutate(() => assert.fail("Concurrent mutation ran")));

    uploaded.resolve({ accepted: ["new.md"] });
    await Promise.resolve();
    assert.equal(controller.state().busy, true);
    update.resolve([{ name: "new.md", processed: false }]);
    await mutation;
    assert.equal(controller.state().busy, false);
    assert.equal(controller.state().canProcess, true);
});

test("a failed mutation releases its local lock for status reconciliation", async (t) => {
    const { controller } = setup(t, {});
    controller.setBusy(false);
    await assert.rejects(controller.mutate(async () => { throw new Error("offline"); }), /offline/);
    assert.equal(controller.state().busy, false);
});

test("late selection responses cannot replace the document currently selected", async (t) => {
    const first = deferred();
    const second = deferred();
    const shown = [];
    const { controller } = setup(t, {
        document: (name) => name === "first.md" ? first.promise : second.promise,
    }, {
        show: (name) => shown.push(name),
    });
    const a = controller.select("first.md");
    const b = controller.select("second.md");
    second.resolve({ result: {}, source: { text: "second" } });
    await b;
    first.resolve({ result: {}, source: { text: "first" } });
    await a;
    assert.deepEqual(shown, ["second.md"]);
});
