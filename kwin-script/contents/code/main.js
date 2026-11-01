// ThunderTray: a minimized Thunderbird window leaves the taskbar and switcher,
// and comes back when it is restored by any means. The tray icon drives this
// script through the shortcuts registered at the bottom of this file.

const TRAY_SERVICE = "org.thundertray.Tray";
const TRAY_PATH = "/Tray";

function isThunderbird(w) {
    return w.normalWindow && !w.transient &&
        /thunderbird/i.test([w.resourceClass, w.resourceName, w.desktopFileName].join(" "));
}

function thunderbirdWindows(except) {
    const found = [];
    const stack = workspace.stackingOrder;
    for (let i = 0; i < stack.length; i++) {
        if (stack[i] !== except && isThunderbird(stack[i])) {
            found.push(stack[i]);
        }
    }
    return found; // bottom to top
}

// The state is sent as a string because D-Bus matches on signature, and a JS
// number can reach it as either an int or a double.
function report(except) {
    const all = thunderbirdWindows(except);
    const hidden = all.filter(function (w) { return w.minimized; }).length;
    callDBus(TRAY_SERVICE, TRAY_PATH, TRAY_SERVICE, "SetState", all.length + " " + hidden);
}

function setSkipped(w, skipped) {
    w.skipTaskbar = skipped;
    w.skipSwitcher = skipped;
    w.skipPager = skipped;
}

function applyState(w) {
    if (!w.minimized) {
        setSkipped(w, false);
        report();
        return;
    }
    // Without a tray icon there would be no way back to a hidden window, so
    // only hide it if the tray is running. Otherwise it minimizes normally.
    callDBus("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", TRAY_SERVICE, function (trayRunning) {
            if (trayRunning && w.minimized) {
                setSkipped(w, true);
            }
            report();
        });
}

function watch(w) {
    if (isThunderbird(w)) {
        w.minimizedChanged.connect(function () { applyState(w); });
        applyState(w);
    }
}

function show() {
    const all = thunderbirdWindows();
    all.forEach(function (w) { w.minimized = false; });
    if (all.length > 0) {
        workspace.activeWindow = all[all.length - 1];
    }
}

function hide(windows) {
    windows.forEach(function (w) { w.minimized = true; });
}

function toggle() {
    const visible = thunderbirdWindows().filter(function (w) { return !w.minimized; });
    if (visible.length === 0) {
        show();
    } else if (visible.indexOf(workspace.activeWindow) >= 0) {
        hide(visible);
    } else {
        workspace.activeWindow = visible[visible.length - 1];
    }
}

function quit() {
    thunderbirdWindows().forEach(function (w) {
        w.minimized = false;
        w.closeWindow();
    });
}

function sync() {
    thunderbirdWindows().forEach(applyState);
    report();
}

workspace.windowAdded.connect(watch);
workspace.windowRemoved.connect(function (w) {
    if (isThunderbird(w)) {
        report(w);
    }
});

registerShortcut("ThunderTray Toggle", "ThunderTray: Show or hide Thunderbird", "", toggle);
registerShortcut("ThunderTray Show", "ThunderTray: Show Thunderbird", "", show);
registerShortcut("ThunderTray Quit", "ThunderTray: Quit Thunderbird", "", quit);
registerShortcut("ThunderTray Sync", "ThunderTray: Resend state to the tray icon", "", sync);

thunderbirdWindows().forEach(watch);
report();
