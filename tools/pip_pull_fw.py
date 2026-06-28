#!/usr/bin/env python3
"""Pull /pipboy.bin + /pipboy.crc (ground-truth firmware) over the REPL."""
import serial,time,base64,os,sys
ser=serial.Serial("/dev/ttyACM1",9600,timeout=0.2); time.sleep(0.3)
OUT="/home/thebu/newhome/projects/pip-boy/dump"; STX=b"\x02"; ETX=b"\x03"
def pcall(e,hard=30):
    ser.reset_input_buffer()
    ser.write(("print(String.fromCharCode(2)+("+e+")+String.fromCharCode(3))\r\n").encode());ser.flush()
    b=bytearray();dl=time.time()+hard
    while time.time()<dl:
        n=ser.in_waiting
        if n:
            b+=ser.read(n);i=b.find(STX)
            if i!=-1 and b.find(ETX,i+1)!=-1:break
        else:time.sleep(0.01)
    i=b.find(STX);j=b.find(ETX,i+1) if i!=-1 else -1
    if i==-1 or j==-1: raise RuntimeError("no sentinel: %r"%bytes(b)[-160:])
    return bytes(b[i+1:j]).decode("utf-8","replace")
def fetch(path,chunk=2048):
    size=int(pcall("''+require('fs').statSync(%r).size"%path))
    pcall("(global._f=E.openFile(%r,'r'))?1:0"%path)
    d=bytearray()
    while len(d)<size:
        n=min(chunk,size-len(d))
        d+=base64.b64decode("".join(pcall("btoa(_f.read(%d))"%n).split()),validate=True)
        sys.stdout.write("\r  %s %d/%d"%(path,len(d),size));sys.stdout.flush()
    pcall("(_f.close(),1)");print()
    return bytes(d)
ser.write(b"\r\n");ser.flush();time.sleep(0.2);ser.reset_input_buffer()
import hashlib
for t in ["/pipboy.bin","/pipboy.crc"]:
    d=fetch(t); p=os.path.join(OUT,"SD"+t.replace("/","_"))
    open(p,"wb").write(d)
    print("  saved %s (%d bytes) sha256=%s"%(p,len(d),hashlib.sha256(d).hexdigest()))
ser.close();print("FW pull done")
