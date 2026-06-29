#!/usr/bin/env python3
"""Live SPCX (SpaceX) stock ticker uplink for the Pip-Boy 3000 Mk V.

Polls a free Yahoo Finance endpoint for the SPCX quote + intraday price series
and pushes them to the device over the Espruino serial REPL, where the on-device
'SPCX' app (USER/spcx.js) renders the graph with the green/scanline CRT effect.

The device runs its OWN watchdog: if this uplink stops (process killed, cable
pulled, wifi drop) for longer than the device timeout, the Pip-Boy shows a
flashing OFFLINE banner by itself -- offline detection does not depend on us.

Usage:
  pip_ticker.py                 # feed the app (must already be launched on device)
  pip_ticker.py --inject        # push USER/spcx.js live first, then feed
  pip_ticker.py --period 20     # seconds between polls (default 20)
  pip_ticker.py --symbol SPCX   # any Yahoo symbol
"""
import serial, serial.tools.list_ports, glob, time, base64, json, argparse, os, sys, urllib.request

BAUD=9600
PIP_USB=(0x0483,0xA4F1)        # The Wand Company "Pip-Boy" USB CDC (vid,pid)
STX=b"\x02"; ETX=b"\x03"
APP_JS=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","dump","spcx.js")

def find_port(explicit=None):
    """Locate the Pip-Boy serial port. Port numbers shuffle across replug/reboot,
    so prefer the stable USB identity; fall back to probing the REPL."""
    if explicit: return explicit
    for p in serial.tools.list_ports.comports():
        if (p.vid,p.pid)==PIP_USB or (p.product and "pip-boy" in p.product.lower()):
            return p.device
    for dev in sorted(glob.glob("/dev/ttyACM*")):     # fallback: ask each ACM if it's a Pip
        try:
            s=connect(dev)
            hit="PIPBOY" in pcall(s,"(process.env.BOARD||'')",hard=3)
            s.close()
            if hit: return dev
        except Exception:
            try: s.close()
            except Exception: pass
    raise RuntimeError("Pip-Boy not found (looked for USB %04x:%04x / 'Pip-Boy', then probed ttyACM*)"%PIP_USB)

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

def inject_app(ser, path):
    """Load a JS source file onto the device via chunked base64 + eval."""
    src=open(path,"rb").read()
    pcall(ser,"(global._src='',1)")
    b64=base64.b64encode(src).decode()
    for k in range(0,len(b64),512):
        pcall(ser,"(_src+='%s',1)"%b64[k:k+512])
    pcall(ser,"(eval(atob(_src)),delete global._src,'ok')",hard=15)

def fetch(symbol):
    """Return (quote_dict, series_list). Tries intraday, falls back to daily."""
    def get(url):
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=12) as r:
            return json.load(r)["chart"]["result"][0]
    base="https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=%s&range=%s"
    res=get(base%(symbol,"5m","1d"))
    closes=[c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes)<2:                              # weekend / pre-IPO gap -> daily
        res=get(base%(symbol,"1d","1mo"))
        closes=[c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes)>60:                             # keep graph smooth but under fillPoly's 64-pt cap
        step=(len(closes)-1)/59.0
        closes=[closes[round(i*step)] for i in range(59)]+[closes[-1]]
    m=res["meta"]
    now=time.time(); tp=m.get("currentTradingPeriod",{})
    def within(p):
        p=tp.get(p,{}); return p and p.get("start",0)<=now<p.get("end",0)
    state=("OPEN" if within("regular") else "PRE" if within("pre")
           else "AFTER" if within("post") else "CLOSED")
    q={"price":m.get("regularMarketPrice",closes[-1]),
       "prev":m.get("chartPreviousClose",m.get("previousClose",closes[0])),
       "hi":m.get("regularMarketDayHigh",max(closes)),
       "lo":m.get("regularMarketDayLow",min(closes)),
       "vol":m.get("regularMarketVolume",0), "state":state}
    return q, [round(c,2) for c in closes]

def push(ser, q, series):
    # Build the history array on-device in short chunks: long REPL input lines
    # (no flow control at 9600) drop characters, so never send the whole array at once.
    ts=time.strftime("%H:%M:%S")
    pcall(ser,"(global._h=[],1)")
    for k in range(0,len(series),12):
        pcall(ser,"(_h.push(%s),1)"%",".join("%.2f"%c for c in series[k:k+12]))
    expr=("(STK.update(%.2f,%.2f,%.2f,%.2f,%d,'%s','%s',_h),'ok')"
          %(q["price"],q["prev"],q["hi"],q["lo"],int(q["vol"]),q["state"],ts))
    return pcall(ser, expr, hard=15)

def app_alive(ser):
    # The live render loop (_blit) is the truth that the app is running on-screen.
    # STK lingers after exit, so don't gate on it.
    try: return pcall(ser,"typeof _blit",hard=4).strip()=="number"
    except Exception: return False

def open_device(a):
    """Find + open the Pip-Boy.  With --inject we own the app and launch it; without
    it we are a pure feeder and wait for the app to be launched from the Apps menu --
    crucial, because heavy console traffic during the device-side eval of a menu launch
    is what froze it.  We only push once the render loop is confirmed alive."""
    port=find_port(a.port)
    ser=connect(port)
    if a.inject:
        print("  injecting app onto",port,"..."); inject_app(ser,APP_JS)
    elif app_alive(ser):
        print("  feeding app already running on",port)
    else:
        print("  waiting for SPCX app on %s -- launch it from Apps (or use --inject)"%port)
    return ser

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",default=None,help="serial port (default: autodetect by USB id)")
    ap.add_argument("--symbol",default="SPCX")
    ap.add_argument("--period",type=float,default=20.0); ap.add_argument("--inject",action="store_true")
    a=ap.parse_args()
    ser=open_device(a)
    print("uplink live: %s every %gs  (Ctrl-C to stop -> device goes OFFLINE)"%(a.symbol,a.period))
    waiting=False
    while True:
        t0=time.time()
        try:
            if not app_alive(ser):
                # App not on screen (user exited, or hasn't launched yet).  Do NOT push
                # -- a heavy STK.update colliding with a menu launch is what froze it.
                if a.inject:
                    print("  %s app gone -> relaunching"%time.strftime("%H:%M:%S")); inject_app(ser,APP_JS)
                else:
                    if not waiting: print("  %s app not running; waiting for launch..."%time.strftime("%H:%M:%S"))
                    waiting=True; time.sleep(min(a.period,4)); continue
            waiting=False
            q,series=fetch(a.symbol)
            push(ser,q,series)
            chg=q["price"]-q["prev"]; pct=chg/q["prev"]*100 if q["prev"] else 0
            print("  %s  $%.2f  %+.2f (%+.2f%%)  %s  %d pts"
                  %(time.strftime("%H:%M:%S"),q["price"],chg,pct,q["state"],len(series)))
        except (serial.SerialException, OSError) as e:
            # port vanished (replug/reboot shuffles ttyACM numbers) -> re-detect & reconnect
            print("  serial lost:",str(e)[:80],"- re-detecting port...")
            try: ser.close()
            except Exception: pass
            time.sleep(2)
            try: ser=open_device(a); print("  reconnected.")
            except Exception as e2: print("  reconnect failed:",str(e2)[:100]); time.sleep(3)
            continue
        except Exception as e:
            print("  fetch/push error:",str(e)[:120],"(device will show OFFLINE if this persists)")
        dt=a.period-(time.time()-t0)
        if dt>0: time.sleep(dt)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: print("\nuplink stopped.")
