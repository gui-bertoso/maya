"""KWin window control through short-lived, acknowledged scripting calls."""
import json
import os
import tempfile
import uuid
from pathlib import Path
from PySide6.QtCore import QObject, QEventLoop, QTimer, Slot, ClassInfo
from PySide6.QtDBus import QDBusConnection, QDBusInterface


@ClassInfo(**{'D-Bus Interface': 'org.maya.WindowControl'})
class KWinControl(QObject):
    def __init__(self):
        super().__init__()
        self.bus = QDBusConnection.sessionBus()
        self.service = f'org.maya.WindowControl.p{os.getpid()}'
        self.path = '/MayaWindowControl'
        self.result = None
        self.loop = None
        if not self.bus.registerService(self.service):
            raise RuntimeError(self.bus.lastError().message())
        if not self.bus.registerObject(self.path, self, QDBusConnection.ExportAllSlots):
            raise RuntimeError(self.bus.lastError().message())
        self.scripting = QDBusInterface('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', self.bus)
        if not self.scripting.isValid():
            raise RuntimeError('KWin scripting service is unavailable')

    @Slot(str)
    def deliver(self, value):
        self.result = json.loads(value)
        if self.loop:
            self.loop.quit()

    def execute(self, body):
        name = 'maya-' + uuid.uuid4().hex
        source = '''var result;
try { result = (function() { BODY })(); }
catch (e) { result = {error: String(e)}; }
callDBus(SERVICE, PATH, "org.maya.WindowControl", "deliver", JSON.stringify(result));
'''.replace('BODY', body).replace('SERVICE', json.dumps(self.service)).replace('PATH', json.dumps(self.path))
        with tempfile.TemporaryDirectory(prefix='maya-kwin-') as folder:
            path = Path(folder) / 'control.js'
            path.write_text(source)
            reply = self.scripting.call('loadScript', str(path), name)
            if reply.errorMessage() or not reply.arguments() or int(reply.arguments()[0]) < 0:
                raise RuntimeError(reply.errorMessage() or 'KWin rejected the window script')
            script_id = int(reply.arguments()[0])
            self.result = None
            self.loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(self.loop.quit)
            try:
                script = QDBusInterface('org.kde.KWin', f'/Scripting/Script{script_id}', 'org.kde.kwin.Script', self.bus)
                reply = script.call('run')
                if reply.errorMessage():
                    raise RuntimeError(reply.errorMessage())
                if self.result is None:
                    timer.start(1500)
                    self.loop.exec()
                if self.result is None:
                    raise RuntimeError('KWin window command timed out')
                if isinstance(self.result, dict) and 'error' in self.result:
                    raise RuntimeError(self.result['error'])
                return self.result
            finally:
                timer.stop()
                self.loop = None
                self.scripting.call('unloadScript', name)

    def windows(self):
        return self.execute('''return workspace.windowList().filter(w => w.normalWindow).map(w => ({
            id: String(w.internalId), title: w.caption, app: String(w.resourceClass),
            pid: w.pid, active: w === workspace.activeWindow }));''')

    def window(self, window_id, action=''):
        return self.execute('''var w = workspace.windowList().find(w => String(w.internalId) === ID);
if (!w) throw new Error("The selected window was closed.");
ACTION
var g = w.frameGeometry;
return [g.x, g.y, g.x + g.width, g.y + g.height];'''.replace('ID', json.dumps(str(window_id))).replace('ACTION', action))

    def move(self, window_id, x, y):
        return self.window(window_id, '''if (!w.moveable) throw new Error("This window cannot be moved.");
w.setMaximize(false, false);
var g = w.frameGeometry;
var width = g.width; var height = g.height;
w.frameGeometry = {x: X, y: Y, width: width, height: height};'''.replace('X', str(int(x))).replace('Y', str(int(y))))
