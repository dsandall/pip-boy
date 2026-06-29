#!/usr/bin/env python3
"""Fetch SD-card files from the Pip-Boy over the Espruino REPL (read-only).
Binary-safe chunked base64 via \\x02..\\x03 sentinels.

Port is autodetected by USB identity (like pip_ticker.py), so it survives the
ttyACM renumbering across replug/reboot. Output lands in ../dump next to the
other extraction artifacts.

Usage:
  pip_fetch_sd.py                       # default diagnostic set (incl. crash log)
  pip_fetch_sd.py /LOGS/exceptions.log  # fetch specific path(s)
  pip_fetch_sd.py --port /dev/ttyACM0   # force a port
"""
import serial, serial.tools.list_ports, glob, time, base64, os, sys, argparse

BAUD=9600
PIP_USB=(0x0483,0xA4F1)
STX=b"\x02"; ETX=b"\x03"
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","dump")

# When launching the SPCX app freezes on "Loading", the truth is here: the live
# on-device copies (which may differ from the repo if an inject wrote a bad file)
# and the firmware's exception log naming the actual throw.
DEFAULT_TARGETS=["/LOGS/exceptions.log","/USER/spcx.js","/APPINFO/spcx.info",
                 "/settings.json","/VERSION"]

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

def pcall(ser, expr, hard=60.0):
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

def fetch_sd(ser, path, chunk=2048):
    size=int(pcall(ser,"''+require('fs').statSync(%r).size"%path))
    pcall(ser,"(global._f=E.openFile(%r,'r'))?1:0"%path)   # global: persists across REPL lines
    data=bytearray()
    while len(data)<size:
        n=min(chunk,size-len(data))
        b64="".join(pcall(ser,"btoa(_f.read(%d))"%n).split())
        data+=base64.b64decode(b64, validate=True)
        sys.stdout.write("\r  %s %d/%d"%(path,len(data),size)); sys.stdout.flush()
    pcall(ser,"(_f.close(),1)"); print()
    return bytes(data)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("targets",nargs="*",default=None,help="SD paths to fetch (default: diagnostic set)")
    ap.add_argument("--port",default=None)
    a=ap.parse_args()
    targets=a.targets or DEFAULT_TARGETS
    os.makedirs(OUT,exist_ok=True)
    ser=connect(find_port(a.port))
    ser.write(b"\r\n"); ser.flush(); time.sleep(0.2); ser.reset_input_buffer()
    for t in targets:
        try:
            d=fetch_sd(ser,t)
            local=os.path.join(OUT,"SD"+t.replace("/","_"))
            open(local,"wb").write(d)
            print("  saved %s (%d bytes)"%(local,len(d)))
        except Exception as e:
            print("  ERR %s: %s"%(t,str(e)[:160]))
    ser.close(); print("done")

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: print()
