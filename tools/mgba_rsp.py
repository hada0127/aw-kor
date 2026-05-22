import socket, time

class RSP:
    def __init__(self, host="127.0.0.1", port=2345):
        self.s = socket.create_connection((host, port), timeout=5)
        self.s.settimeout(5)
        # drain initial
        try:
            self.s.recv(4096)
        except Exception:
            pass

    def _cksum(self, data):
        return sum(data) & 0xFF

    def send(self, body):
        if isinstance(body, str):
            body = body.encode()
        pkt = b'$' + body + b'#' + b'%02x' % self._cksum(body)
        self.s.sendall(pkt)

    def recv(self):
        buf = b''
        while True:
            # already have a full packet?
            h = buf.find(b'$')
            if h >= 0:
                e = buf.find(b'#', h + 1)
                if e >= 0 and len(buf) >= e + 3:
                    body = buf[h+1:e]
                    self.s.sendall(b'+')  # ack their packet
                    return body
            try:
                c = self.s.recv(8192)
            except socket.timeout:
                return buf
            if not c:
                return buf
            buf += c

    def cmd(self, body):
        self.send(body)
        return self.recv()

    def cont(self):
        # continue without waiting for stop
        self.send('c')

    def interrupt(self):
        self.s.sendall(b'\x03')
        return self.recv()

    def read_regs(self):
        r = self.cmd('g').decode(errors='replace')
        # ARM: 16 regs (r0-r15) little-endian hex, then cpsr
        regs = []
        for i in range(0, min(len(r), 16*8), 8):
            hexw = r[i:i+8]
            try:
                regs.append(int.from_bytes(bytes.fromhex(hexw), 'little'))
            except Exception:
                regs.append(None)
        return regs

    def read_mem(self, addr, length):
        out = bytearray()
        chunk = 0x400
        while length > 0:
            n = min(chunk, length)
            r = self.cmd('m%x,%x' % (addr, n))
            try:
                out += bytes.fromhex(r.decode())
            except Exception:
                break
            addr += n; length -= n
        return bytes(out)

    def write_mem(self, addr, data):
        hx = data.hex()
        return self.cmd('M%x,%x:%s' % (addr, len(data), hx))

    def set_wwatch(self, addr, length=4):
        return self.cmd('Z2,%x,%x' % (addr, length))

    def clr_wwatch(self, addr, length=4):
        return self.cmd('z2,%x,%x' % (addr, length))

    def close(self):
        try: self.s.close()
        except Exception: pass
