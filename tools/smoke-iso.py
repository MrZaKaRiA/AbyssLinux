#!/usr/bin/env python3
"""Boot an ARM64 Abyss live ISO and verify a shell through QEMU user networking.

Requires QEMU with HVF and AArch64 firmware. Runs only the live system; it does
not attach or modify an installation disk. No software is installed in the VM.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time


def qmp(sock, command, arguments=None):
    request = {'execute': command}
    if arguments is not None:
        request['arguments'] = arguments
    sock.write((json.dumps(request) + '\n').encode())
    while True:
        reply = json.loads(sock.readline())
        if 'error' in reply:
            raise RuntimeError(str(reply['error']))
        if 'return' in reply:
            return reply['return']


def send(sock, key):
    qmp(sock, 'human-monitor-command', {'command-line': 'sendkey ' + key})
    time.sleep(0.06)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iso', type=Path)
    parser.add_argument('--firmware', required=True, type=Path)
    parser.add_argument('--qemu', default='qemu-system-aarch64')
    parser.add_argument('--wait', type=int, default=90, help='seconds to allow live desktop to start')
    parser.add_argument('--candidate', action='store_true', help='also check the lock listener, Void locker group, and recorder')
    parser.add_argument('--failure-screenshot', type=Path, help='save a PPM screenshot on timeout')
    args = parser.parse_args()
    if not args.iso.is_file() or not args.firmware.is_file():
        parser.error('ISO and firmware must exist')
    with tempfile.TemporaryDirectory(prefix='abyss-smoke-', dir='/tmp') as temp:
        qmp_path = temp + '/qmp'
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(20)
        port = listener.getsockname()[1]
        command = [args.qemu, '-M', 'virt,accel=hvf', '-cpu', 'host', '-smp', '4', '-m', '3072',
                   '-bios', str(args.firmware.resolve()), '-device', 'virtio-gpu-pci', '-device', 'qemu-xhci',
                   '-device', 'usb-kbd', '-device', 'usb-tablet', '-drive',
                   f'file={args.iso.resolve()},media=cdrom,readonly=on', '-netdev', 'user,id=n0',
                   '-device', 'virtio-net-pci,netdev=n0', '-display', 'none', '-serial', 'none',
                   '-qmp', f'unix:{qmp_path},server=on,wait=off']
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            end = time.monotonic() + 15
            while not os.path.exists(qmp_path):
                if process.poll() is not None:
                    raise RuntimeError('QEMU failed to start: ' + process.stderr.read().decode(errors='replace'))
                if time.monotonic() >= end:
                    raise RuntimeError('Timed out waiting for QEMU monitor')
                time.sleep(0.1)
            connection = socket.socket(socket.AF_UNIX)
            connection.connect(qmp_path)
            stream = connection.makefile('rwb', buffering=0)
            json.loads(stream.readline())
            qmp(stream, 'qmp_capabilities')
            print(f'Waiting {args.wait} seconds for the live desktop...', flush=True)
            time.sleep(args.wait)
            # The first-run dmenu grabs the keyboard until dismissed.
            send(stream, 'esc')
            time.sleep(1)
            send(stream, 'meta_l-ret')
            time.sleep(3)
            checks = 'pgrep xss >/dev/null && getent group nogroup >/dev/null && test -x /usr/bin/abyss-record && ' if args.candidate else ''
            text = checks + f'echo abyssok >/dev/tcp/10.0.2.2/{port}'
            keys = {' ': 'spc', '>': 'shift-dot', '/': 'slash', '.': 'dot', '-': 'minus', '&': 'shift-7'}
            for char in text:
                send(stream, keys.get(char, char))
            send(stream, 'ret')
            try:
                client, _ = listener.accept()
            except TimeoutError as exc:
                if args.failure_screenshot:
                    qmp(stream, 'screendump', {'filename': str(args.failure_screenshot.resolve())})
                raise RuntimeError('Timed out waiting for the guest shell; check the VM screenshot and boot time') from exc
            with client:
                message = client.recv(128).strip()
            if message != b'abyssok':
                raise RuntimeError(f'Unexpected guest response: {message!r}')
            print('PASS: live desktop opened a terminal and executed a shell command')
            if args.candidate:
                print('PASS: lock listener, locker group, and recorder are present')
        finally:
            listener.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
