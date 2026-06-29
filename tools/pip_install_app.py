#!/usr/bin/env python3
"""Install a custom app onto the Pip-Boy SD card over the Espruino REPL.

Writes a local JS file to USER/<name>.js and (if present) its APPINFO/<name>.info,
so the app launches from the Apps menu on its own -- no host-side inject needed.
The firmware launches apps via `eval(fs.readFile("USER/"+app))`, so a stale or
truncated USER/<name>.js is what makes a launch freeze; this replaces it cleanly
and verifies the write byte-for-byte (9600 baud with no flow control drops chars
on long lines, so every write is chunked and read back).

Usage:
  pip_install_app.py dump/spcx.js                 # -> USER/spcx.js (+ APPINFO/spcx.info if alongside)
  pip_install_app.py dump/spcx.js --name spcx     # force the on-SD name
  pip_install_app.py dump/spcx.js --no-info        # skip the .info
  pip_install_app.py dump/spcx.js --launch         # eval it after install (simulate menu launch)
"""
import serial, serial.tools.list_ports, glob, time, base64, os, sys, argparse

BAUD=9600
PIP_USB=(0x0483,0xA4F1)
STX=b"\x02"; ETX=b"\x03"

def find_port(explicit=None):
    if explicit: return explicit
    for p in serial.tools.list_ports.comports():
        if (p.vid,p.pid)==PIP_USB or (p.product and "pip-boy" in p.product.lower()):
            return p.device
    cands=sorted(glob.glob("/dev/ttyACM*"))
    if len(cands)==1: return cands[0]
    raise RuntimeError("Pip-Boy not found (USB %04x:%04x); pass --port"%PIP_USB)

def connect(port):
    s=serial.Serial(port,BAUD,timeout=0.2); time.sleep(0.3)
    for _ in range(3):                       # Ctrl-C clears any partial REPL input
        s.write(b"\x03"); s.flush(); time.sleep(0.12)
        s.write(b"\r\n"); s.flush(); time.sleep(0.12)
        s.read(s.in_waiting or 1)
    s.reset_input_buffer(); return s

def pcall(ser, expr, hard=20.0):
    ser.reset_input_buffer()
    ser.write(("print(String.fromCharCode(2)+("+expr+")+String.fromCharCode(3))\r\n").encode()); ser.flush()
    buf=bytearray(); dl=time.time()+hard
    while time.time()<dl:
        n=ser.in_waiting
        if n:
            buf+=ser.read(n); i=buf.find(STX)
            if i!=-1 and buf.find(ETX,i+1)!=-1: break
        else: time.sleep(0.01)
    i=buf.find(STX); j=buf.find(ETX,i+1) if i!=-1 else -1
    if i==-1 or j==-1: raise RuntimeError("no sentinel: %r"%bytes(buf)[-160:])
    return bytes(buf[i+1:j]).decode("utf-8","replace")

def write_sd(ser, path, data):
    """Write bytes to an SD path via chunked base64 -> atob -> File.write."""
    b64=base64.b64encode(data).decode()
    pcall(ser,"(global._w=E.openFile(%r,'w'))?1:0"%path)
    try:
        for k in range(0,len(b64),512):                # 512 is a multiple of 4: each slice decodes cleanly
            pcall(ser,"(_w.write(atob('%s')),1)"%b64[k:k+512])
            sys.stdout.write("\r  writing %s %d/%d"%(path,min(k+512,len(b64)),len(b64))); sys.stdout.flush()
    finally:
        pcall(ser,"(_w.close(),1)")
    print()

def read_sd(ser, path, chunk=2048):
    size=int(pcall(ser,"''+require('fs').statSync(%r).size"%path))
    pcall(ser,"(global._f=E.openFile(%r,'r'))?1:0"%path)
    data=bytearray()
    while len(data)<size:
        n=min(chunk,size-len(data))
        b64="".join(pcall(ser,"btoa(_f.read(%d))"%n).split())
        data+=base64.b64decode(b64, validate=True)
    pcall(ser,"(_f.close(),1)")
    return bytes(data)

def install(ser, local, sd_path):
    data=open(local,"rb").read()
    print("  %s -> %s (%d bytes)"%(local,sd_path,len(data)))
    write_sd(ser,sd_path,data)
    back=read_sd(ser,sd_path)
    if back==data:
        print("  verified OK (%d bytes match)"%len(back)); return True
    print("  VERIFY FAILED: wrote %d, read back %d bytes"%(len(data),len(back))); return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("jsfile",help="local app .js to install")
    ap.add_argument("--name",default=None,help="on-SD app name (default: js basename without .js)")
    ap.add_argument("--info",default=None,help="local .info file (default: <name>.info beside the js)")
    ap.add_argument("--no-info",action="store_true",help="don't install an APPINFO/*.info")
    ap.add_argument("--launch",action="store_true",help="eval the installed file after writing (simulate menu launch)")
    ap.add_argument("--port",default=None)
    a=ap.parse_args()

    name=a.name or os.path.splitext(os.path.basename(a.jsfile))[0]
    info_local=a.info or os.path.join(os.path.dirname(os.path.abspath(a.jsfile)),name+".info")

    ser=connect(find_port(a.port))
    ser.write(b"\r\n"); ser.flush(); time.sleep(0.2); ser.reset_input_buffer()

    ok=install(ser,a.jsfile,"USER/%s.js"%name)
    if not a.no_info and os.path.exists(info_local):
        ok=install(ser,info_local,"APPINFO/%s.info"%name) and ok
    elif not a.no_info:
        print("  (no .info at %s -- skipping; pass --info or --no-info)"%info_local)

    if ok and a.launch:
        print("  launch test: eval(fs.readFile('USER/%s.js')) ..."%name)
        r=pcall(ser,"(eval(require('fs').readFile('USER/%s.js')),'launched-ok')"%name,hard=15)
        print("    ->",r.strip())

    ser.close()
    print("done" if ok else "DONE WITH ERRORS")
    sys.exit(0 if ok else 1)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: print()
