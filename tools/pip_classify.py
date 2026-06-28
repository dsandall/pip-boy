#!/usr/bin/env python3
"""Classify Pip.* members as native-C vs JS, and pull one JS func's source."""
import serial, time, re, os
PORT="/dev/ttyACM1"; OUT="/home/thebu/pipboy_dump"
ser=serial.Serial(PORT,9600,timeout=0.2); time.sleep(0.3)
STX=b"\x02"; ETX=b"\x03"
def pcall(expr, hard=20.0):
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
ser.write(b"\r\n"); ser.flush(); time.sleep(0.2); ser.reset_input_buffer()

# Build a {name: native?/js?/value-type} table for every key of Pip
classify=("Object.keys(Pip).map(function(k){var v;try{v=Pip[k]}catch(e){return k+'\\tERR'}"
          "if(typeof v=='function'){var s=''+v;return k+'\\t'+(s.indexOf('[native code]')>=0?'NATIVE':'JS')}"
          "return k+'\\t'+typeof v}).join('\\n')")
table=pcall(classify, hard=30)
open(os.path.join(OUT,"Pip_members.tsv"),"w").write(table)
nat=[l for l in table.splitlines() if l.endswith("NATIVE")]
js =[l for l in table.splitlines() if l.endswith("\tJS")]
print("Pip members: %d native, %d JS-defined, %d other"%(len(nat),len(js),
      len(table.splitlines())-len(nat)-len(js)))
print("\n--- NATIVE (compiled C primitives) ---")
print(", ".join(l.split("\t")[0] for l in nat))
print("\n--- JS-defined (in FW.JS) ---")
print(", ".join(l.split("\t")[0] for l in js))

# Prove detokenisation: pull readable source of one representative JS function
for cand in ["showMainMenu","saveSettings","configureAlarm","updateBrightness","offAnimation"]:
    src=pcall("(typeof Pip.%s=='function'&&(''+Pip.%s).indexOf('[native')<0)?(''+Pip.%s):''"%(cand,cand,cand),hard=20)
    if src.strip():
        print("\n--- readable source: Pip.%s (detokenised by interpreter) ---"%cand)
        print(src[:900])
        open(os.path.join(OUT,"sample_%s.js"%cand),"w").write(src)
        break
ser.close()
