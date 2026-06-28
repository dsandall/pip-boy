#!/usr/bin/env python3
"""Fetch specific SD-card files from the Pip-Boy over the Espruino REPL.
Binary-safe chunked base64 via \\x02..\\x03 sentinels. Read-only."""
import serial, time, base64, os, sys, re
PORT="/dev/ttyACM1"; OUT="/home/thebu/pipboy_dump"
os.makedirs(OUT, exist_ok=True)
ser=serial.Serial(PORT,9600,timeout=0.2); time.sleep(0.3)
STX=b"\x02"; ETX=b"\x03"
def pcall(expr, hard=60.0):
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

def fetch_sd(path, chunk=2048):
    size=int(pcall("''+require('fs').statSync(%r).size"%path))
    # GLOBAL handle (no 'var', no IIFE) so it persists across REPL lines
    pcall("(global._f=E.openFile(%r,'r'))?1:0"%path)
    data=bytearray()
    while len(data)<size:
        n=min(chunk,size-len(data))
        b64="".join(pcall("btoa(_f.read(%d))"%n).split())
        data+=base64.b64decode(b64, validate=True)
        sys.stdout.write("\r  %s %d/%d"%(path,len(data),size)); sys.stdout.flush()
    pcall("(_f.close(),1)")
    print()
    return bytes(data)

ser.write(b"\r\n"); ser.flush(); time.sleep(0.2); ser.reset_input_buffer()

targets=["/fwupdate.js","/settings.json","/VERSION",
         "/USER/asteroid.js","/USER/customimg.js","/USER/text.js","/USER/text.txt",
         "/APPINFO/asteroid.info","/APPINFO/customimg.info","/APPINFO/text.info",
         "/FW.JS"]
for t in targets:
    try:
        d=fetch_sd(t)
        local=os.path.join(OUT,"SD"+t.replace("/","_"))
        open(local,"wb").write(d)
        print("  saved %s (%d bytes)"%(local,len(d)))
    except Exception as e:
        print("  ERR %s: %s"%(t,e))
ser.close(); print("done")
