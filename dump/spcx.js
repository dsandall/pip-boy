// SPCX live stock ticker for Pip-Boy 3000 Mk V.  Graph is the primary focus.
// Renders into an offscreen 2bpp buffer and Pip.blitImage()s it so the firmware
// applies the green phosphor palette + animated scanlines.  The HOST pushes
// quotes+history via STK.update(...); a device-side watchdog flips to a flashing
// OFFLINE banner if no update arrives within STK.timeout sec.
//
// IMPORTANT (v2): the heavy full-frame render runs ONLY when data changes.  When
// OFFLINE we just flash a small top strip -- re-rendering the whole graph twice a
// second saturates the interpreter and starves knob/console input (v1 bug: the
// device wedged with "dials do nothing" once the uplink dropped).
if (Pip.removeSubmenu) Pip.removeSubmenu();
if (Pip.remove) Pip.remove();
{
  global.STK = {
    sym:"SPCX", name:"Space Exploration Technologies",
    price:0, prev:0, hi:0, lo:0, vol:0, state:"", ts:"--:--:--", hist:[],
    lastSeen:0, timeout:35, online:false, flash:0, gotData:false
  };

  var G = Graphics.createArrayBuffer(400,300,2,{msb:true,
    buffer:E.toArrayBuffer(E.memoryArea(0x10000000+32768,(400*300)/4))});
  global._TG = G;

  // The physical display has rounded corners that clip the buffer's corners.
  // Inset corner-anchored content by PAD so nothing important lands in the curve.
  // Bump this if anything still gets cut.
  var PAD = 18;
  global._setPad = function(p){ PAD=p; renderContent(); };   // live-tune from REPL

  function fvol(v){
    if (v>=1e9) return (v/1e9).toFixed(2)+"B";
    if (v>=1e6) return (v/1e6).toFixed(1)+"M";
    if (v>=1e3) return (v/1e3).toFixed(1)+"K";
    return ""+v;
  }
  function arrow(x,y,up,col){
    G.setColor(col);
    if (up) G.fillPoly([x,y+13, x+8,y, x+16,y+13]);
    else    G.fillPoly([x,y,    x+16,y, x+8,y+13]);
  }

  // The hero: a filled price line graph with a dashed prev-close reference.
  function graph(s,prev,x,y,w,h){
    var n = s ? s.length : 0;
    G.setColor(1).drawRect(x,y,x+w,y+h);
    if (n<2){
      G.setColor(2).setFontMonofonto18().setFontAlign(0,0)
       .drawString("acquiring data...",x+w/2,y+h/2).setFontAlign(-1,-1);
      return;
    }
    var tlo=s[0], thi=s[0], i;
    for (i=1;i<n;i++){ if(s[i]<tlo)tlo=s[i]; if(s[i]>thi)thi=s[i]; }
    var lo=tlo, hi=thi;
    if (prev){ if(prev<lo)lo=prev; if(prev>hi)hi=prev; }
    var pad=(hi-lo)*0.08 || 1; lo-=pad; hi+=pad;
    var rng=hi-lo;
    var X=function(i){ return x + (n==1?0:i*w/(n-1)); };
    var Y=function(v){ return y+h - (v-lo)/rng*h; };
    G.setColor(1);
    if (n<=61){
      var poly=[x,y+h];
      for (i=0;i<n;i++){ poly.push(X(i)|0, Y(s[i])|0); }
      poly.push(x+w,y+h);
      G.fillPoly(poly);
    } else {
      for (i=0;i<n;i++){ var xx=X(i)|0; G.drawLine(xx,Y(s[i])|0,xx,y+h-1); }
    }
    if (prev){
      var yr=Y(prev)|0; G.setColor(2);
      for (var dx=x; dx<x+w; dx+=9) G.drawLine(dx,yr,dx+4,yr);
    }
    G.setColor(3);
    for (i=1;i<n;i++) G.drawLine(X(i-1)|0,Y(s[i-1])|0,X(i)|0,Y(s[i])|0);
    G.fillCircle(X(n-1)|0, Y(s[n-1])|0, 3);
    G.setColor(2).setFontMonofonto18();
    G.setFontAlign(1,-1).drawString(thi.toFixed(2), x+w-3, y+2);
    G.setFontAlign(1, 1).drawString(tlo.toFixed(2), x+w-3, y+h-2);
    G.setFontAlign(-1,-1);
  }

  // Heavy: full frame.  Called only on a data update, NOT on every flash tick.
  function renderContent(){
    var d=STK; G.clear();
    var L=PAD, R=400-PAD;                 // left / right content edges (corner-safe)
    var chg=d.price-d.prev, pct=d.prev?chg/d.prev*100:0, up=chg>=0;
    G.setFontAlign(-1,-1);
    // header line 1: SYMBOL (left) ... $PRICE (right)
    G.setColor(3).setFontMonofonto36().drawString(d.sym,L,6);
    G.setFontAlign(1,-1).drawString(d.gotData?("$"+d.price.toFixed(2)):"$ --.--",R,6).setFontAlign(-1,-1);
    // header line 2: name (left, truncated) ... arrow +chg (+pct%) (right)
    G.setColor(2).setFontMonofonto18();
    if (d.gotData){
      var ct=(up?"+":"")+chg.toFixed(2)+" ("+(up?"+":"")+pct.toFixed(2)+"%)";
      var cw=G.stringWidth(ct), ax=R-cw-20;
      var nm=d.name, maxw=ax-L-6;
      while (nm.length>3 && G.stringWidth(nm)>maxw) nm=nm.slice(0,-1);
      if (nm!==d.name) nm=nm.slice(0,-1)+".";
      G.setColor(2).drawString(nm,L,48);
      arrow(ax,50,up,up?3:2);
      G.setColor(up?3:2).setFontAlign(1,-1).drawString(ct,R,48).setFontAlign(-1,-1);
    } else {
      G.drawString(d.name,L,48);
    }
    // THE GRAPH (primary focus)
    graph(d.hist, d.prev, L, 74, R-L, 178);
    // footer: day range + volume (left), update time (right)
    G.setColor(2).setFontMonofonto18()
     .drawString("DAY "+d.lo.toFixed(2)+"-"+d.hi.toFixed(2)+"   VOL "+fvol(d.vol),L,262);
    G.setColor(1).setFontAlign(1,-1).drawString(d.ts,R,262).setFontAlign(-1,-1);
  }
  global._render = renderContent;

  // Cheap: just the top strip.  Called on the flash tick while OFFLINE.
  function drawBanner(){
    var L=PAD, R=400-PAD;
    if (STK.flash&1){ G.setColor(3).fillRect(L,4,R,34); G.setColor(0); }
    else           { G.setColor(1).fillRect(L,4,R,34); G.setColor(3); }
    G.setFontMonofonto23().setFontAlign(0,-1)
     .drawString("/!\\ OFFLINE - NO UPLINK",200,8).setFontAlign(-1,-1);
  }

  // Host calls this each poll; pets the watchdog.  hist = array of closes.
  STK.update = function(price,prev,hi,lo,vol,state,ts,hist){
    STK.price=price; STK.prev=prev; STK.hi=hi; STK.lo=lo; STK.vol=vol;
    STK.state=state; STK.ts=ts; if (hist&&hist.length) STK.hist=hist;
    STK.gotData=true; STK.lastSeen=getTime(); STK.online=true;
    renderContent();                 // heavy redraw only here (~every poll)
  };

  // Watchdog: cheap.  Flip OFFLINE on staleness; flash only the banner strip.
  global._wd = setInterval(function(){
    try {
      if (STK.online && (getTime()-STK.lastSeen) > STK.timeout) STK.online=false;
      if (!STK.online){ STK.flash^=1; drawBanner(); }
    } catch(e){}
  }, 1000);

  // Re-blit so the firmware's moving scan band keeps animating (light: 20fps).
  global._blit = setInterval(function(){ try { Pip.blitImage(G,40,11); } catch(e){} }, 50);

  // Exit on a knob TURN only -- exactly like the stock Custom Image app.  Do NOT
  // bind 'select'/'press'/'button': those are the launch/navigation button, and the
  // very press that launched us would re-enter this handler mid menu-dispatch and
  // wedge the load.  (That was the "freeze on loading spcx.js" bug.)
  var EVENTS=["knob1","knob2"];
  // Pip.remove = teardown ONLY (no navigation).  The menu/launcher calls this on
  // transitions, so it must NOT call showMainMenu() -- doing so recurses back into
  // here (menu teardown -> Pip.remove -> showMainMenu -> ...) and overflows the stack.
  global._tickCleanup = function(){
    try { if (global._wd)   clearInterval(_wd);   } catch(e){} global._wd=undefined;
    try { if (global._blit) clearInterval(_blit); } catch(e){} global._blit=undefined;
    EVENTS.forEach(function(ev){ try { Pip.removeListener(ev,_tickExit); } catch(e){} });
    try { g.clear(); } catch(e){}
  };
  // Knob handler: guard against re-entry, tear down, drop Pip.remove so the menu
  // can't re-enter us, THEN navigate back to the apps menu.
  global._tickExit = function(){
    if (STK._exiting) return; STK._exiting=true;
    _tickCleanup();
    try { delete Pip.remove; } catch(e){ Pip.remove=undefined; }
    try { if (typeof showMainMenu=="function") showMainMenu(); } catch(e){}
    try { if (typeof submenuApps=="function") submenuApps(); } catch(e){}
  };
  Pip.remove = _tickCleanup;         // teardown-only; safe for the launcher to call
  EVENTS.forEach(function(ev){ try { Pip.on(ev,_tickExit); } catch(e){} });

  renderContent();                   // initial frame -> OFFLINE banner until first push
}
