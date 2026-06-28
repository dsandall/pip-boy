#!/usr/bin/env python3
"""Dump Pip-Boy program artifacts over the Espruino REPL (read-only).
Uses print() with @@..## sentinels to defeat the interactive inspector's
'head ... tail' abbreviation. Strict base64 decode. No flashing/reset."""
import serial, time, base64, os, sys, re

PORT="/dev/ttyACM1"; OUT="/home/thebu/newhome/projects/pip-boy/dump"
os.makedirs(OUT, exist_ok=True)
ser=serial.Serial(PORT,9600,timeout=0.2); time.sleep(0.3)

def drain(settle=0.2,hard=3.0):
    buf=bytearray(); start=last=time.time()
    while True:
        n=ser.in_waiting
        if n: buf+=ser.read(n); last=time.time()
        elif time.time()-last>settle: break
        else: time.sleep(0.01)
        if time.time()-start>hard: break
    return bytes(buf)

STX=b"\x02"; ETX=b"\x03"
def pcall(expr, hard=60.0):
    """Wrap output in \\x02 ... \\x03 control bytes (emitted only by print(),
    never present in the echoed source) and read until ETX arrives."""
    ser.reset_input_buffer()
    cmd="print(String.fromCharCode(2)+("+expr+")+String.fromCharCode(3))\r\n"
    ser.write(cmd.encode()); ser.flush()
    buf=bytearray(); deadline=time.time()+hard
    while time.time()<deadline:
        n=ser.in_waiting
        if n:
            buf+=ser.read(n)
            i=buf.find(STX)
            if i!=-1 and buf.find(ETX, i+1)!=-1:
                break
        else:
            time.sleep(0.01)
    i=buf.find(STX); j=buf.find(ETX, i+1) if i!=-1 else -1
    if i==-1 or j==-1:
        raise RuntimeError("no sentinel; got: %r"%bytes(buf)[-200:])
    return bytes(buf[i+1:j]).decode("utf-8","replace")

def b64chunks(jsstr, size, chunk=2048, label=""):
    data=bytearray(); off=0
    while off<size:
        n=min(chunk,size-off)
        b64="".join(pcall("btoa((%s).substr(%d,%d))"%(jsstr,off,n)).split())
        data+=base64.b64decode(b64, validate=True)   # strict: raises on garbage
        off+=n
        sys.stdout.write("\r  %s %d/%d"%(label,off,size)); sys.stdout.flush()
    print(); return bytes(data)

ser.write(b"\r\n"); ser.flush(); drain()

# sanity: print() must NOT abbreviate a long string
t=pcall("'X'.repeat(3000)")
print("print() long-string test: got %d chars, abbreviated=%s"%(len(t), '...' in t))

# ---- .bootcde ----
print("\n== .bootcde ==")
sz=int(pcall("''+require('Storage').read('.bootcde').length"))
print("  length =",sz)
body=b64chunks("require('Storage').read('.bootcde')", sz, label=".bootcde")
open(os.path.join(OUT,".bootcde"),"wb").write(body)
print("  saved %d bytes  (matches=%s)"%(len(body), len(body)==sz))

open(os.path.join(OUT,"STORAGE_VERSION.txt"),"w").write(pcall("require('Storage').read('VERSION')"))

# ---- recursive SD manifest ----
print("\n== SD manifest ==")
walk=("(function(){var fs=require('fs'),o=[];"
      "function w(p){var l;try{l=fs.readdirSync(p)}catch(e){return}"
      "l.forEach(function(f){if(f=='.'||f=='..')return;var fp=(p=='/'?'':p)+'/'+f,st;"
      "try{st=fs.statSync(fp)}catch(e){o.push(fp+'\\t?');return}"
      "if(st.dir){o.push(fp+'/\\t<dir>');w(fp)}else{o.push(fp+'\\t'+st.size)}});}"
      "w('/');return o.join('\\n')})()")
man=pcall(walk, hard=90.0)
open(os.path.join(OUT,"SD_manifest.txt"),"w").write(man)
print(man)

ser.close(); print("\nDump dir:",OUT)
