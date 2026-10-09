// =====================================================================
// Mapa de Maringá (d3): limite municipal, loteamentos, destaque do
// bairro de cada caso, zoom e arraste. Usa MGA (docs/geo-maringa.js).
// =====================================================================
const W = 960, H = 760;
const svg = d3.select("#map").attr("viewBox", `0 0 ${W} ${H}`);
const LIM = MGA.limite;
const BAIRROS = MGA.bairros.features.filter(f=>d3.geoArea(f) < 0.01);
const proj = d3.geoMercator().fitExtent([[20,20],[W-20,H-20]], LIM);
const path = d3.geoPath(proj);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const clipRect = svg.append("defs").append("clipPath").attr("id","frame").append("rect").attr("width",W).attr("height",H);
const root = svg.append("g").attr("clip-path","url(#frame)");
const gOv = svg.append("g").attr("class","overlay").style("pointer-events","none");   // escala e norte
const zg = root.append("g");
const gLim = zg.append("g"), gB = zg.append("g"), gHi = zg.append("g"), gLab = zg.append("g"), gPts = zg.append("g");
const tip = document.getElementById("tip");
const titleCase = s => s.toLowerCase().replace(/(^|\s)(\S)/g,(m,a,b)=>a+b.toUpperCase()).replace(/\b(De|Da|Do|Das|Dos|E)\b/g,w=>w.toLowerCase());
let k = 1;
let u = 1;                 // unidades do viewBox por pixel de tela (mantém tamanhos fixos na tela)
let VB = [0, 0, W, H];     // viewBox atual, ajustado à proporção da área do mapa

/* faz o mapa preencher a área toda, sem faixas vazias, qualquer que seja o formato da tela */
function ajustarVB(){
  const r = svg.node().getBoundingClientRect();
  if(!r.width || !r.height) return;
  const ar = r.width / r.height;
  let w = W, h = H;
  if(ar > W/H) w = H*ar; else h = W/ar;
  VB = [(W-w)/2, (H-h)/2, w, h];
  u = w / r.width;
  svg.attr("viewBox", VB.join(" "));
  clipRect.attr("x",VB[0]).attr("y",VB[1]).attr("width",VB[2]).attr("height",VB[3]);
  applyScale(); desenharEscala();
}

/* barra de escala (km) e indicação do norte, sempre no canto da figura */
const KM_POR_UNIDADE = d3.geoDistance(proj.invert([W/2,H/2]), proj.invert([W/2+100,H/2])) * 6371 / 100;
function desenharEscala(){
  gOv.selectAll("*").remove();
  const alvo = 120*u*KM_POR_UNIDADE/k;                       // ~120 px de tela, em km
  const km = [0.1,0.25,0.5,1,2,5,10,20].filter(v=>v<=alvo).pop() || 0.1;
  const len = km*k/KM_POR_UNIDADE;
  const x0 = VB[0]+16*u, y0 = VB[1]+VB[3]-18*u, cor = css("--ink"), fonte = "IBM Plex Sans, sans-serif";
  const g = gOv.append("g");
  g.append("rect").attr("x",x0-8*u).attr("y",y0-24*u).attr("width",Math.max(len,40*u)+16*u).attr("height",30*u)
    .attr("rx",4*u).attr("fill",css("--land-out")).attr("fill-opacity",.85);
  g.append("rect").attr("x",x0).attr("y",y0-4*u).attr("width",len/2).attr("height",4*u).attr("fill",cor);
  g.append("rect").attr("x",x0+len/2).attr("y",y0-4*u).attr("width",len/2).attr("height",4*u).attr("fill","none").attr("stroke",cor).attr("stroke-width",u);
  g.append("text").attr("x",x0).attr("y",y0-9*u).attr("fill",cor).attr("font-size",12*u).attr("font-family",fonte)
    .text(km<1 ? `${Math.round(km*1000)} m` : `${String(km).replace(".",",")} km`);
  const nx = VB[0]+VB[2]-26*u, ny = VB[1]+18*u;
  gOv.append("path").attr("d",`M${nx},${ny} l${7*u},${20*u} l${-7*u},${-5*u} l${-7*u},${5*u} z`).attr("fill",cor);
  gOv.append("text").attr("x",nx).attr("y",ny+34*u).attr("text-anchor","middle").attr("fill",cor)
    .attr("font-size",12*u).attr("font-weight",600).attr("font-family",fonte).text("N");
}

function showTip(evt, html){
  const box = document.querySelector(".mapa-area").getBoundingClientRect();
  tip.innerHTML = html;
  tip.style.left = Math.max(4, Math.min(evt.clientX - box.left + 12, box.width - 250)) + "px";
  tip.style.top = (evt.clientY - box.top - 40) + "px";
  tip.style.opacity = 1;
}
const hideTip = ()=> tip.style.opacity = 0;

function drawMap(){
  [gLim,gB,gLab].forEach(g=>g.selectAll("*").remove());
  gLim.append("path").datum(LIM).attr("d",path).attr("fill",css("--land"))
    .attr("stroke",css("--ink")).attr("class","lim").attr("stroke-linejoin","round");
  gB.selectAll("path").data(BAIRROS).join("path").attr("d",path)
    .attr("fill",css("--panel")).attr("fill-opacity",.55)
    .attr("stroke",css("--muted")).attr("stroke-opacity",.45).attr("class","bp")
    .on("mousemove",(e,d)=>{ if(d.properties.n) showTip(e, esc(titleCase(d.properties.n))); })
    .on("mouseleave",hideTip);
  const c = proj([-51.9386,-23.4253]);
  gLab.append("circle").attr("cx",c[0]).attr("cy",c[1]).attr("class","cat").attr("fill",css("--ink"));
  gLab.append("text").attr("x",c[0]).attr("y",c[1]).attr("class","catl").attr("fill",css("--ink"))
    .attr("font-family","IBM Plex Sans, sans-serif").text("Catedral");
  applyScale();
}

function drawPoints(){
  const list = visible().filter(c=>c.coords);
  gHi.selectAll("*").remove();
  list.forEach(c=>{
    gHi.selectAll(null).data(BAIRROS.filter(b=>(c.bairros_mapa||[c.bairro]).includes(b.properties.n))).join("path")
      .attr("d",path).attr("class","hi")
      .attr("fill", c.tipo==="consumado"?css("--plum"):css("--lilac")).attr("fill-opacity",.35)
      .attr("stroke", c.tipo==="consumado"?css("--plum"):css("--lilac"))
      .style("pointer-events","none");
  });
  const sel = gPts.selectAll("g.pt").data(list, d=>d.id);
  sel.exit().remove();
  const enter = sel.enter().append("g").attr("class","pt").attr("tabindex",0).attr("role","button").style("cursor","pointer");
  enter.append("circle");
  const all = enter.merge(sel);
  all.attr("data-x", d=>proj(d.coords)[0]).attr("data-y", d=>proj(d.coords)[1])
     .attr("aria-label", d=>`${d.titulo}, ${d.data.split("-").reverse().join("/")}, ${titleCase(d.bairro)}. Ver na linha do tempo`);
  all.select("circle")
     .attr("fill", d=> d.tipo==="consumado"?css("--plum"):css("--panel"))
     .attr("stroke", d=> d.tipo==="consumado"?css("--panel"):css("--lilac"));
  all.on("mousemove focus", (e,d)=>{
      const ev = e.clientX!==undefined ? e : (()=>{const r=e.currentTarget.getBoundingClientRect();return {clientX:r.left+r.width/2,clientY:r.top};})();
      showTip(ev, `<strong>${esc(d.titulo)}</strong><br>${d.data.split("-").reverse().join("/")} · ${esc(titleCase(d.bairro))}`);
    })
    .on("mouseleave blur", hideTip)
    .on("click keydown", (e,d)=>{
      if(e.type==="keydown" && e.key!=="Enter" && e.key!==" ") return;
      e.preventDefault();
      const el = document.getElementById("c-"+d.id);
      if(!el) return;
      el.scrollIntoView({block:"center"});
      el.classList.add("flash"); setTimeout(()=>el.classList.remove("flash"),1600);
    });
  applyScale();
}

/* mantém espessuras e tamanhos constantes na tela durante o zoom */
function applyScale(){
  const f = u/k;
  gLim.selectAll(".lim").attr("stroke-width",1.6*f);
  gB.selectAll(".bp").attr("stroke-width",.6*f);
  gHi.selectAll(".hi").attr("stroke-width",1.8*f);
  gLab.selectAll(".cat").attr("r",3*f);
  gLab.selectAll(".catl").attr("font-size",12*f).attr("dx",6*f).attr("dy",4*f);
  gPts.selectAll("g.pt").attr("transform", function(){ return `translate(${this.dataset.x},${this.dataset.y}) scale(${f})`; });
  gPts.selectAll("circle").attr("r", d=> d.tipo==="consumado"?9:8).attr("stroke-width", d=> d.tipo==="consumado"?2:3.5);
}

const zoom = d3.zoom().scaleExtent([1,40]).translateExtent([[-W,-H],[2*W,2*H]])
  .on("zoom", e=>{ zg.attr("transform", e.transform); k = e.transform.k; applyScale(); desenharEscala(); hideTip(); });
svg.call(zoom).on("dblclick.zoom", null);

function frame(bounds, pad=30){
  const [[x0,y0],[x1,y1]] = bounds;
  const s = Math.min(40, 0.92/Math.max((x1-x0)/(VB[2]-pad), (y1-y0)/(VB[3]-pad)));
  return d3.zoomIdentity.translate(W/2,H/2).scale(s).translate(-(x0+x1)/2,-(y0+y1)/2);
}
function urbanBounds(){
  // núcleo urbano contínuo: loteamentos dentro do retângulo da sede (exclui distritos)
  const core = BAIRROS.filter(b=>{ const [x,y]=d3.geoCentroid(b); return x>-52.02 && x<-51.86 && y>-23.49 && y<-23.34; });
  return path.bounds({type:"FeatureCollection",features:core});
}
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function go(t){ (reduced? svg : svg.transition().duration(600)).call(zoom.transform, t); }
function setFrameBtn(id){ ["zUrb","zMun"].forEach(x=>document.getElementById(x).setAttribute("aria-pressed", String(x===id))); }
document.getElementById("zUrb").onclick = ()=>{ setFrameBtn("zUrb"); go(frame(urbanBounds())); };
document.getElementById("zMun").onclick = ()=>{ setFrameBtn("zMun"); go(d3.zoomIdentity); };
document.getElementById("zIn").onclick = ()=> svg.transition().duration(reduced?0:250).call(zoom.scaleBy,1.6);
document.getElementById("zOut").onclick = ()=> svg.transition().duration(reduced?0:250).call(zoom.scaleBy,1/1.6);

/* acompanha mudanças de tamanho da janela ou da área do mapa */
ajustarVB();
if(window.ResizeObserver) new ResizeObserver(()=>ajustarVB()).observe(document.querySelector(".mapa-area"));
