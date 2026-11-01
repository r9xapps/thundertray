// Runs the KWin script against a fake KWin. Usage: node tests/test_kwin_script.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function signal() {
    const handlers = [];
    return {
        connect: (f) => handlers.push(f),
        emit: (...args) => handlers.forEach((f) => f(...args)),
    };
}

function fakeWindow(props) {
    const changed = signal();
    let minimized = !!props.minimized;
    return {
        normalWindow: true, transient: false, resourceClass: "thunderbird", resourceName: "",
        desktopFileName: "", skipTaskbar: false, skipSwitcher: false, skipPager: false,
        closed: false,
        closeWindow() { this.closed = true; },
        ...props,
        minimizedChanged: changed,
        get minimized() { return minimized; },
        set minimized(v) { if (v !== minimized) { minimized = v; changed.emit(); } },
    };
}

function load(windows, trayRunning = true) {
    const shortcuts = {};
    const states = [];
    const workspace = {
        stackingOrder: windows, activeWindow: null, windowAdded: signal(), windowRemoved: signal(),
    };
    const context = {
        workspace,
        registerShortcut: (name, text, keys, f) => { shortcuts[name] = f; },
        callDBus: (service, objectPath, iface, method, arg, callback) => {
            if (method === "NameHasOwner") callback(trayRunning);
            else if (method === "SetState") states.push(arg);
            else throw new Error("unexpected call " + method);
        },
    };
    const file = path.join(__dirname, "../kwin-script/contents/code/main.js");
    vm.runInNewContext(fs.readFileSync(file, "utf8"), context);
    return { shortcuts, states, workspace, last: () => states[states.length - 1] };
}

function test(name, f) {
    f();
    console.log("ok - " + name);
}

test("minimizing hides from the taskbar and restoring brings it back", () => {
    const w = fakeWindow({});
    const k = load([w]);
    w.minimized = true;
    assert.deepStrictEqual([w.skipTaskbar, w.skipSwitcher, w.skipPager], [true, true, true]);
    assert.strictEqual(k.last(), "1 1");
    w.minimized = false;
    assert.deepStrictEqual([w.skipTaskbar, w.skipSwitcher, w.skipPager], [false, false, false]);
    assert.strictEqual(k.last(), "1 0");
});

test("a window stays in the taskbar when the tray is not running", () => {
    const w = fakeWindow({});
    load([w], false);
    w.minimized = true;
    assert.strictEqual(w.skipTaskbar, false);
});

test("other apps, dialogs and non-normal windows are ignored", () => {
    const others = [
        fakeWindow({ resourceClass: "firefox" }),
        fakeWindow({ transient: true }),
        fakeWindow({ normalWindow: false }),
    ];
    const k = load(others);
    others.forEach((w) => { w.minimized = true; assert.strictEqual(w.skipTaskbar, false); });
    assert.strictEqual(k.last(), "0 0");
});

test("the Flatpak app id is recognized", () => {
    const w = fakeWindow({ resourceClass: "org.mozilla.Thunderbird" });
    load([w]);
    w.minimized = true;
    assert.strictEqual(w.skipTaskbar, true);
});

test("windows opened after startup are handled", () => {
    const k = load([]);
    const w = fakeWindow({});
    k.workspace.stackingOrder.push(w);
    k.workspace.windowAdded.emit(w);
    assert.strictEqual(k.last(), "1 0");
    w.minimized = true;
    assert.strictEqual(w.skipTaskbar, true);
});

test("closing a window updates the count", () => {
    const w = fakeWindow({});
    const k = load([w]);
    k.workspace.windowRemoved.emit(w);
    assert.strictEqual(k.last(), "0 0");
});

test("an already minimized window is hidden when the script starts", () => {
    const w = fakeWindow({ minimized: true });
    const k = load([w]);
    assert.strictEqual(w.skipTaskbar, true);
    assert.strictEqual(k.last(), "1 1");
});

test("toggle hides when focused, restores when hidden, raises when unfocused", () => {
    const a = fakeWindow({});
    const b = fakeWindow({});
    const other = fakeWindow({ resourceClass: "firefox" });
    const k = load([a, b, other]);
    const toggle = k.shortcuts["ThunderTray Toggle"];

    k.workspace.activeWindow = b;
    toggle();
    assert.deepStrictEqual([a.minimized, b.minimized], [true, true]);
    assert.strictEqual(other.minimized, false);

    k.workspace.activeWindow = other;
    toggle();
    assert.deepStrictEqual([a.minimized, b.minimized], [false, false]);
    assert.strictEqual(k.workspace.activeWindow, b);

    k.workspace.activeWindow = other;
    toggle();
    assert.deepStrictEqual([a.minimized, b.minimized], [false, false]);
    assert.strictEqual(k.workspace.activeWindow, b);
});

test("quit restores and closes every window", () => {
    const w = fakeWindow({ minimized: true });
    const k = load([w]);
    k.shortcuts["ThunderTray Quit"]();
    assert.strictEqual(w.minimized, false);
    assert.strictEqual(w.closed, true);
});

test("sync resends the state", () => {
    const w = fakeWindow({});
    const k = load([w]);
    k.states.length = 0;
    k.shortcuts["ThunderTray Sync"]();
    assert.strictEqual(k.last(), "1 0");
});
