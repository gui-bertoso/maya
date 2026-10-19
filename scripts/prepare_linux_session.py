"""Give python-xlib a session-local auth record for the current hostname.

KDE can keep the login hostname in Xauthority after the hostname changes.
Qt accepts its wildcard entry, while python-xlib only checks exact hostnames.
The existing session credential stays local, in a private runtime file.
"""
import os
import socket
import struct
from pathlib import Path
from Xlib.xauth import Xauthority

source = Path(os.environ['XAUTHORITY'])
auth = Xauthority(str(source))
host = socket.gethostname().encode()
entries = list(auth.entries)
for family, address, number, name, data in auth.entries:
    if family == 256 and address != host:
        entries.append((family, host, number, name, data))
if entries == auth.entries:
    print(source)
else:
    target = Path(os.environ['XDG_RUNTIME_DIR']) / 'maya-session.Xauthority'
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        for family, *fields in entries:
            stream.write(struct.pack('!H', family))
            for field in fields:
                stream.write(struct.pack('!H', len(field)) + field)
    print(target)
