/* Sharpe Lab · entrada de la portada, al estilo de matmilitar.es:
   las letras de SHARPE LAB se dibujan, se rellenan y se deshacen en partículas que forman
   la presentación del proyecto (estrategias, backtests, en vivo).
   Solo en la portada (sin #ancla), una vez por sesión (sessionStorage sl_in). */
(function(){
"use strict";
var hp=location.hash.replace(/^#\/?/,'');
var seen=false; try{seen=sessionStorage.getItem('sl_in')==='1';}catch(e){seen=true;}
if(seen) return;
try{sessionStorage.setItem('sl_in','1');}catch(e){}
if(hp) return; /* enlace directo a una sección: sin entrada */
var RM=false; try{RM=matchMedia('(prefers-reduced-motion: reduce)').matches;}catch(e){}
var DE=document.documentElement; DE.classList.add('sli-on');
var css='html.sli-on{background:#040505}html.sli-on,html.sli-on body{overflow:hidden!important}html.sli-on body>*:not(#sli){visibility:hidden}'+
'#sli{position:fixed;inset:0;z-index:1000;background:radial-gradient(120% 80% at 50% 45%,#161a1c 0%,#0b0c0d 55%,#040505 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden;transition:opacity .6s ease,transform .6s ease;color:#e9e9e6;font:16px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-tap-highlight-color:transparent}'+
'#sli.out{opacity:0;transform:scale(1.04);pointer-events:none}#sli.out.rm{transform:none}'+
'#sli:before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,255,255,.018) 0 1px,transparent 1px 4px);pointer-events:none}'+
'#sli svg{display:block;width:100%;flex:1 1 auto;min-height:0;max-width:1400px}'+
'#sli .slib{flex:0 0 auto;width:100%;display:flex;flex-direction:column;align-items:center;padding:6px 24px max(28px,calc(env(safe-area-inset-bottom) + 18px))}'+
'#sli .slid{margin:0 0 14px;color:#6f767c;font:400 12px/1.4 inherit;font-family:inherit;letter-spacing:.12em;text-align:center;opacity:0;transition:opacity .5s}#sli .slid span{display:inline-block}'+
'#sli .slid.on{opacity:1}'+
'#sli button{outline:none!important;box-shadow:none!important;font-variant:normal!important;font-family:inherit!important;-webkit-appearance:none;appearance:none;margin:0}'+
'#sli .sligo{min-width:220px;min-height:52px;background:rgba(143,154,106,.18)!important;border:1px solid #b3bd8c!important;color:#f1f1ee!important;font-size:15px;line-height:1;font-weight:600!important;letter-spacing:.24em;text-transform:uppercase;border-radius:4px!important;cursor:pointer;padding:0 22px;opacity:0;transform:translateY(8px);transition:opacity .5s,transform .5s,background .2s}'+
'#sli .sligo.on{opacity:1;transform:none}#sli .sligo:hover,#sli .sligo:focus-visible{background:rgba(143,154,106,.34)!important;color:#f1f1ee!important}'+
'#sli .slisk{position:absolute;top:max(12px,env(safe-area-inset-top));right:12px;min-height:44px;min-width:44px;padding:0 14px;background:transparent!important;border:0!important;color:#9aa0a6!important;font-size:14px;line-height:1;font-weight:500!important;letter-spacing:.12em;cursor:pointer;border-radius:4px!important;z-index:2}'+
'#sli .slisk:hover,#sli .slisk:focus-visible{color:#f1f1ee!important;background:rgba(255,255,255,.06)!important}';
var st=document.createElement('style'); st.textContent=css; (document.head||DE).appendChild(st);

/* ---------- letras (caja local x ±50, y ±65) ---------- */
var LET={
 S:'M50-65V-40H-24V-12H50V65H-50V40H24V12H-50V-65Z',
 H:'M-50-65H-24V-13H24V-65H50V65H24V13H-24V65H-50Z',
 A:'M-52 65L-14-65H14L52 65H26L18 36H-18L-26 65ZM-11 14H11L0-28Z',
 R:'M-50-65H26L50-41V-1L33 11L52 65H25L8 16H-24V65H-50ZM-24-41H18L24-35V-14L18-8H-24Z',
 P:'M-50-65H26L50-41V-3L26 21H-24V65H-50ZM-24-41H18L24-35V-9L18-3H-24Z',
 E:'M-50-65H50V-40H-24V-13H40V12H-24V40H50V65H-50Z',
 L:'M-50-65H-24V40H50V65H-50Z',
 B:'M-50-65H26L48-43V-14L37-2L50 10V43L28 65H-50ZM-24-41H16L22-35V-19L16-13H-24ZM-24 11H20L26 17V35L20 41H-24Z'
};
var WORD='SHARPELAB', GRP=[0,0,0,1,1,1,2,2,2];
var NS='http://www.w3.org/2000/svg';
function E2(tag,at,par){ var e=document.createElementNS(NS,tag); for(var k in at) e.setAttribute(k,at[k]); if(par) par.appendChild(e); return e; }

var POR=(window.innerWidth||400)/(window.innerHeight||700)<0.95;
var VB=POR?[400,800]:[1200,560];
function row(n,cx,y,w,gap,extra){ var tot=n*w+(n-1)*gap+(extra||0), x0=cx-tot/2+w/2, r=[]; for(var k=0;k<n;k++) r.push([x0+k*(w+gap)+(extra&&k>=6?extra:0),y]); return r; }
var LAY=POR?{
 mark:[200,64,20], let:row(6,200,352,52,9).concat(row(3,200,462,52,9)), ls:.52,
 sl:[{x:200,y:172,s:.78},{x:200,y:402,s:.78},{x:200,y:632,s:.78}],
 cap:[262,492,722], f1:21, f2:12.5
}:{
 mark:[600,64,30], let:row(9,600,270,92,20,40), ls:.92,
 sl:[{x:268,y:262,s:.98},{x:600,y:262,s:.98},{x:932,y:262,s:.98}],
 cap:[430,430,430], f1:24, f2:15
};
var CAPS=[['STRATEGIES','Fixed rules · long or cash'],['BACKTESTS','10 years of data · with costs'],['LIVE','Paper money · updated nightly']];

/* ---------- presentación: velas, curva de capital, señal en vivo (caja local x ±150, y ±85) ---------- */
var CND=[[40,10,0,56],[12,-15,-28,22],[-14,8,-24,20],[6,-30,-42,14],[-28,-55,-66,-20],[-52,-78,-86,-44]];
var EQ=[[-140,55],[-118,47],[-98,52],[-78,30],[-58,37],[-38,10],[-18,19],[2,-5],[22,9],[42,-26],[62,-17],[82,-46],[102,-38],[122,-63],[140,-72]];
function pl(a){ return 'M'+a.map(function(p){return p[0]+' '+p[1];}).join('L'); }

var ov,svg,G={},T0=0,raf=0,done=false,tAuto=RM?3200:10000,seekT=null,pts=[];

function build(){
 if(done) return;
 ov=document.createElement('div'); ov.id='sli'; ov.setAttribute('role','dialog'); ov.setAttribute('aria-label','Sharpe Lab, entrada');
 svg=E2('svg',{viewBox:'0 0 '+VB[0]+' '+VB[1],preserveAspectRatio:'xMidYMid meet','aria-hidden':'true'},ov);
 var d=E2('defs',{},svg); G.d=d;
 LG('slL',[[0,'#ffffff'],[.45,'#c9cdc3'],[.55,'#8b9184'],[1,'#4a4f47']]);
 LG('slS',[[0,'#fff',0],[.5,'#fff',.55],[1,'#fff',0]],1,0);
 LG('slUp',[[0,'#e4e7d2'],[.38,'#a5ac88'],[.62,'#5e6547'],[1,'#272b1f']]);
 LG('slDn',[[0,'#e8c2b8'],[.38,'#b9705f'],[.62,'#7d3a2c'],[1,'#33160f']]);
 LG('slAr',[[0,'#eef2f5',.55],[.4,'#aab5bd',.28],[1,'#5f6b73',0]]);
 LG('slGl',[[0,'#3a5361'],[.45,'#1a2a33'],[1,'#0b141a']]);
 LG('slSea',[[0,'#9fb6c4',0],[.5,'#c9d6dd',.75],[1,'#9fb6c4',0]],1,0);
 RG('slP',[[0,'#fbffe8'],[.4,'#dfe8b8',.8],[1,'#b3bd8c',0]]);
 RG('slAu',[[0,'#fff3c8'],[.35,'#d6b25e',.9],[1,'#d6b25e',0]]);
 var fl=E2('filter',{id:'slG',x:'-20%',y:'-20%',width:'140%',height:'140%'},d);
 E2('feGaussianBlur',{stdDeviation:'2.2',result:'b'},fl); var fm=E2('feMerge',{},fl); E2('feMergeNode',{in:'b'},fm); E2('feMergeNode',{in:'SourceGraphic'},fm);

 /* marca superior */
 G.mark=E2('text',{x:LAY.mark[0]+LAY.mark[2]*.17,y:LAY.mark[1],'text-anchor':'middle',fill:'#e9e9e6','font-size':LAY.mark[2],'font-weight':700,'letter-spacing':'.34em',opacity:0,style:'font-family:inherit'},svg); G.mark.textContent='SHARPE LAB';

 G.sil=[];G.let=[];G.cap=[];
 for(var i=0;i<3;i++){
  var sl=LAY.sl[i];
  var outer=E2('g',{transform:'translate('+sl.x+' '+sl.y+') scale('+sl.s+')'},svg);
  var S={g:outer,in:E2('g',{},outer),main:[]};
  S.fx=E2('g',{opacity:0},S.in); S.body=E2('g',{opacity:0},S.in);
  S.line=E2('g',{fill:'none',stroke:'#dfe6c4','stroke-width':1.4/sl.s,'stroke-linejoin':'round','stroke-linecap':'round',filter:'url(#slG)'},S.in);
  if(i===0) drawCandles(S); else if(i===1) drawCurve(S); else drawLive(S);
  var cp=E2('clipPath',{id:'slC'+i},d);
  S.main.forEach(function(p,k){ p.id='slC'+i+'p'+k; E2('use',{href:'#'+p.id},cp); });
  var sg=E2('g',{'clip-path':'url(#slC'+i+')'},S.in);
  S.sw=E2('rect',{x:-80,y:-200,width:70,height:500,fill:'url(#slS)',opacity:0,transform:'skewX(-20)'},sg);
  S.top=E2('g',{},S.in); if(S.after) S.after(S.top);
  G.sil.push(S);
  var cx=POR?200:sl.x, cy=LAY.cap[i];
  var ct=E2('g',{opacity:0},svg);
  var t1=E2('text',{x:cx+LAY.f1*(POR?.14:.11),y:cy,'text-anchor':'middle','font-size':LAY.f1,'font-weight':700,'letter-spacing':POR?'.28em':'.22em',fill:'#e9e9e6',style:'font-family:inherit'},ct);
  var w=CAPS[i][0]; var a=E2('tspan',{fill:'#d6b25e'},t1); a.textContent=w.charAt(0); var b=E2('tspan',{},t1); b.textContent=w.slice(1);
  var t2=E2('text',{x:cx,y:cy+LAY.f2*1.6,'text-anchor':'middle','font-size':LAY.f2,'letter-spacing':'.12em',fill:'#9aa0a6',style:'font-family:inherit'},ct); t2.textContent=CAPS[i][1];
  G.cap.push(ct);
 }
 for(var k=0;k<WORD.length;k++){
  var lg=E2('g',{},svg);
  var lf=E2('path',{d:LET[WORD[k]],fill:'url(#slL)','fill-rule':'evenodd',opacity:0},lg);
  var ll=E2('path',{d:LET[WORD[k]],fill:'none',stroke:'#eef3da','stroke-width':1.6,'stroke-linejoin':'round',filter:'url(#slG)'},lg);
  G.let.push({g:lg,f:lf,l:ll,i:GRP[k],j:k%3});
 }
 G.pt=E2('g',{opacity:0},svg);
 var sk=document.createElement('button'); sk.className='slisk'; sk.type='button'; sk.textContent='Saltar \u203a'; ov.appendChild(sk);
 var bb=document.createElement('div'); bb.className='slib'; ov.appendChild(bb);
 var dis=document.createElement('p'); dis.className='slid'; dis.lang='en'; dis.innerHTML='<span>A personal learning project \u00b7</span> <span>not investment advice</span>'; bb.appendChild(dis);
 var go=document.createElement('button'); go.className='sligo'; go.type='button'; go.textContent='Entrar'; bb.appendChild(go);
 G.go=go; G.dis=dis;
 sk.addEventListener('click',exit); go.addEventListener('click',exit);
 document.addEventListener('keydown',onKey);
 document.body.appendChild(ov);
 G.let.forEach(function(o){ o.len=o.l.getTotalLength(); o.l.setAttribute('stroke-dasharray',o.len); });
 G.sil.forEach(function(S){ S.lines=[].slice.call(S.line.childNodes).map(function(p){ var n=p.getTotalLength(); p.setAttribute('stroke-dasharray',n); return {p:p,n:n}; }); if(S.prep) S.prep(); });
 var N=POR?12:15;
 G.let.forEach(function(lo){
  var so=G.sil[lo.i].lines[0], arr=[];
  for(var k=0;k<N;k++){
   var a1=lo.l.getPointAtLength(lo.len*k/N), u=((lo.j*N+k)*0.618+0.1)%1, b1=so.p.getPointAtLength(so.n*u);
   var c=E2('circle',{r:POR?2.1:2.6,fill:'url(#slP)'},G.pt);
   arr.push({a:[a1.x,a1.y],b:place(lo.i,b1.x,b1.y),c:c,dl:Math.random()*0.18,arc:(Math.random()-.5)*(POR?90:140)});
  }
  pts.push(arr);
 });
 try{go.focus({preventScroll:true});}catch(e){}
 window.SL_INTRO={seek:function(t){seekT=t;frame(performance.now());},exit:exit};
 T0=performance.now(); raf=requestAnimationFrame(frame);
}
function place(i,x,y){ var sl=LAY.sl[i]; return [sl.x+x*sl.s, sl.y+y*sl.s]; }
function P(par,d,at){ at=at||{}; at.d=d; return E2('path',at,par); }
function LG(id,st,x2,y2){ var g=E2('linearGradient',{id:id,x1:0,y1:0,x2:x2==null?0:x2,y2:y2==null?1:y2},G.d); st.forEach(function(s){ E2('stop',{offset:s[0],'stop-color':s[1],'stop-opacity':s[2]==null?1:s[2]},g); }); }
function RG(id,st){ var g=E2('radialGradient',{id:id},G.d); st.forEach(function(s){ E2('stop',{offset:s[0],'stop-color':s[1],'stop-opacity':s[2]==null?1:s[2]},g); }); }

/* 1 · estrategias: velas japonesas con una media que pasa por encima */
function drawCandles(S){
 var bod='',wk='';
 CND.forEach(function(c,k){ var x=-125+k*50, t=Math.min(c[0],c[1]), b=Math.max(c[0],c[1]);
  bod+='M'+(x-14)+' '+t+'H'+(x+14)+'V'+b+'H'+(x-14)+'Z'; wk+='M'+x+' '+c[2]+'V'+t+'M'+x+' '+b+'V'+c[3];
  var r=P(S.body,'M'+(x-14)+' '+t+'H'+(x+14)+'V'+b+'H'+(x-14)+'Z',{fill:c[1]<c[0]?'url(#slUp)':'url(#slDn)'}); S.main.push(r);
  P(S.body,'M'+(x-14)+' '+t+'H'+(x+14),{stroke:'#fff','stroke-opacity':.5,'stroke-width':1});
  P(S.body,'M'+x+' '+c[2]+'V'+t+'M'+x+' '+b+'V'+c[3],{stroke:'#8b9184','stroke-width':2});
 });
 P(S.line,bod); P(S.line,wk); P(S.line,'M-150 72H150');
 S.ma=P(S.fx,'M-140 46C-100 40-80 20-40 12S20-20 60-40S120-70 145-80',{fill:'none',stroke:'url(#slSea)','stroke-width':2.2,'stroke-dasharray':'10 8'});
 S.dot=E2('circle',{cx:125,cy:-78,r:7,fill:'url(#slAu)'},S.fx);
 E2('circle',{cx:125,cy:-78,r:2.4,fill:'#fff3c8'},S.fx);
}
/* 2 · backtests: curva de capital sobre 10 años */
function drawCurve(S){
 for(var g=0;g<4;g++) P(S.fx,'M-150 '+(-60+g*40)+'H150',{stroke:'#9aa0a6','stroke-opacity':.12,'stroke-width':1});
 var ar=P(S.body,pl(EQ)+'L140 75L-140 75Z',{fill:'url(#slAr)'}); S.main.push(ar);
 S.cv=P(S.body,pl(EQ),{fill:'none',stroke:'#e9ecdc','stroke-width':2.4,'stroke-linejoin':'round'});
 P(S.line,pl(EQ)); P(S.line,'M-150-88V75H150');
 S.prep=function(){ S.cvn=S.cv.getTotalLength(); };
 S.dot=E2('circle',{cx:140,cy:-72,r:8,fill:'url(#slAu)'},S.fx);
 S.dc=E2('circle',{cx:140,cy:-72,r:2.6,fill:'#fff3c8'},S.fx);
}
/* 3 · en vivo: pantalla con la señal latiendo */
function drawLive(S){
 var fr='M-132-80H132Q144-80 144-68V68Q144 80 132 80H-132Q-144 80-144 68V-68Q-144-80-132-80Z';
 var ecg='M-124 18H-64L-52-14L-40 44L-26-52L-12 32L0 18H34L42 6L50 18H124';
 var sc=P(S.body,fr,{fill:'url(#slGl)'}); S.main.push(sc);
 P(S.body,'M-132-80H132',{stroke:'#fff','stroke-opacity':.35,'stroke-width':1});
 for(var g=0;g<5;g++) P(S.body,'M-144 '+(-48+g*24)+'H144',{stroke:'#9fb6c4','stroke-opacity':.07,'stroke-width':1});
 S.ecg=P(S.body,ecg,{fill:'none',stroke:'#b3bd8c','stroke-opacity':.7,'stroke-width':2,'stroke-linejoin':'round'});
 P(S.line,ecg); P(S.line,fr);
 S.after=function(top){
  S.run=P(top,ecg,{fill:'none',stroke:'#f6ffd8','stroke-width':3,'stroke-linejoin':'round','stroke-linecap':'round',filter:'url(#slG)',opacity:0});
  S.rd=E2('circle',{cx:-118,cy:-56,r:5,fill:'#d24a36',opacity:0},top);
  S.lv=E2('text',{x:-106,y:-51.5,'font-size':13,'font-weight':700,'letter-spacing':'.18em',fill:'#e9e9e6',opacity:0,style:'font-family:inherit'},top); S.lv.textContent='LIVE';
 };
 S.prep=function(){ S.rn=S.run.getTotalLength(); S.run.setAttribute('stroke-dasharray','46 '+S.rn); };
}
function cl(x){return x<0?0:x>1?1:x;}
function seg(t,a,b){return cl((t-a)/(b-a));}
function eio(x){return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;}
function eo(x){return 1-Math.pow(1-x,3);}

function frame(now){
 if(done) return;
 var el=now-T0, t=seekT!=null?seekT:(RM?99999:el*0.66), lt=el/1000; /* misma cadencia que matmilitar: la transformación acaba hacia los 5,5 s y el final sigue vivo hasta los 10 s */
 G.mark.setAttribute('opacity',(seg(t,2600,3300)*0.9).toFixed(3));
 for(var k=0;k<G.let.length;k++){
  var L=G.let[k], i=L.i, p0=LAY.let[k], sl=LAY.sl[i];
  var a=k*45, d1=eo(seg(t,a,a+700)), f1=seg(t,a+350,a+950);
  var ms=1250+i*230+L.j*70;
  var mv=eio(seg(t,ms,ms+900)), tx=sl.x+(L.j-1)*34*sl.s, lx=p0[0]+(tx-p0[0])*mv, ly=p0[1]+(sl.y-p0[1])*mv, ls=LAY.ls*(1+0.12*Math.sin(Math.PI*mv));
  L.g.setAttribute('transform','translate('+lx.toFixed(2)+' '+ly.toFixed(2)+') scale('+ls.toFixed(3)+')');
  L.f.setAttribute('opacity',(f1*(1-seg(t,ms+50,ms+600))).toFixed(3));
  L.l.setAttribute('stroke-dashoffset',(L.len*(1-d1+seg(t,ms+150,ms+750))).toFixed(1));
  L.l.setAttribute('opacity',(1-seg(t,ms+600,ms+800)).toFixed(3));
  L.l.setAttribute('stroke-width',(1.6/ls).toFixed(2));
  var pp=pts[k];
  for(var q=0;q<pp.length;q++){
   var o=pp[q], u=eio(seg(t,ms+120+o.dl*900,ms+900+o.dl*900)), vis=u>0&&u<1;
   o.c.setAttribute('opacity',vis?(0.4+0.6*Math.sin(Math.PI*u)).toFixed(2):'0');
   if(vis){ var sx=lx+o.a[0]*ls, sy=ly+o.a[1]*ls, ex=o.b[0], ey=o.b[1], mx=(sx+ex)/2+o.arc*0.3, my=(sy+ey)/2-Math.abs(o.arc)*0.5, w=1-u;
    o.c.setAttribute('cx',(w*w*sx+2*w*u*mx+u*u*ex).toFixed(1)); o.c.setAttribute('cy',(w*w*sy+2*w*u*my+u*u*ey).toFixed(1)); }
  }
 }
 for(var i=0;i<3;i++){
  var S=G.sil[i], ms=1250+i*230+70;
  var od=eo(seg(t,ms+350,ms+1150)), bf=seg(t,ms+800,ms+1350);
  S.lines.forEach(function(o){ o.p.setAttribute('stroke-dashoffset',(o.n*(1-od)).toFixed(1)); });
  S.line.setAttribute('opacity',(od>0?1-0.75*seg(t,ms+1300,ms+1900):0).toFixed(3));
  S.body.setAttribute('opacity',bf.toFixed(3));
  var sw=seg(t,ms+1150,ms+1900);
  S.sw.setAttribute('opacity',sw>0&&sw<1?'1':'0');
  S.sw.setAttribute('x',(-230+520*sw).toFixed(1));
  G.cap[i].setAttribute('opacity',seg(t,ms+1100,ms+1600).toFixed(3));
  var fxo=seg(t,ms+900,ms+1500); S.fx.setAttribute('opacity',fxo.toFixed(3));
  if(i===0){ S.ma.setAttribute('stroke-dashoffset',(RM?0:-(lt*22)%18).toFixed(1));
   var pu=RM?1:0.75+0.25*Math.sin(lt*3.2); S.dot.setAttribute('r',(6+3*pu).toFixed(2)); }
  if(i===1&&S.cvn){ var ph=RM?1:((lt*0.22)%1), pt=S.cv.getPointAtLength(S.cvn*eio(ph));
   S.dot.setAttribute('cx',pt.x.toFixed(1)); S.dot.setAttribute('cy',pt.y.toFixed(1)); S.dc.setAttribute('cx',pt.x.toFixed(1)); S.dc.setAttribute('cy',pt.y.toFixed(1)); }
  if(i===2&&S.rn){ S.run.setAttribute('opacity',RM?'0':fxo.toFixed(3)); S.run.setAttribute('stroke-dashoffset',(S.rn-((lt*150)%(S.rn+46))).toFixed(1));
   var bl=RM?1:(Math.sin(lt*4)>-0.2?1:0.25); S.rd.setAttribute('opacity',(fxo*bl).toFixed(3)); S.lv.setAttribute('opacity',fxo.toFixed(3)); }
 }
 G.pt.setAttribute('opacity',RM?'0':'1');
 if((seekT!=null?t>=2700:el>=3400)||RM){ G.go.classList.add('on'); G.dis.classList.add('on'); }
 if(seekT==null&&el>=tAuto){ exit(); return; }
 if(seekT==null) raf=requestAnimationFrame(frame);
}
function onKey(e){ if(e.key==='Escape') exit(); }
function exit(){
 if(done) return; done=true; cancelAnimationFrame(raf); document.removeEventListener('keydown',onKey);
 if(!ov){ DE.classList.remove('sli-on'); return; }
 if(RM) ov.classList.add('rm'); ov.classList.add('out'); DE.classList.remove('sli-on');
 setTimeout(function(){ if(ov&&ov.parentNode) ov.parentNode.removeChild(ov); },650);
}
if(document.body) build(); else document.addEventListener('DOMContentLoaded',build);
})();
