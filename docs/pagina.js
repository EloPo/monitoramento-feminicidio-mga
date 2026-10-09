// =====================================================================
// Página: contadores, linha do tempo, distribuição das variáveis,
// casos de fora e filtros. Usa CASES, OUTSIDE e UPDATED (js/dados.js).
// =====================================================================
const NI = "Não informado";
const MESES = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"];
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const isNI = v => v === null || v === undefined || v === NI;
const fmtAge = v => isNI(v) ? NI : v + " anos";

document.getElementById("upd").textContent = UPDATED;
document.getElementById("nC").textContent = CASES.filter(c=>c.tipo==="consumado").length;
document.getElementById("nT").textContent = CASES.filter(c=>c.tipo==="tentado").length;

let filter = "todos";
const visible = () => CASES.filter(c => filter==="todos" || c.tipo===filter)
                           .sort((a,b)=> b.data.localeCompare(a.data));

function renderTimeline(){
  const tl = document.getElementById("tl");
  const list = visible();
  if(!list.length){ tl.innerHTML = '<li class="empty">Nenhum caso nesta categoria.</li>'; return; }
  tl.innerHTML = list.map(c=>{
    const [y,m,d] = c.data.split("-");
    const rows = [
      ["Idade da vítima", fmtAge(c.v.idadeV)],
      ["Idade do agressor", fmtAge(c.v.idadeA)],
      ["Relação com o agressor", c.v.relacao],
      ["Meio / arma", c.v.meio],
      ["Local do crime", c.v.local],
      ["Filhos", c.v.filhos],
      ["Antecedentes do agressor", c.v.antecedentes],
      ["Escolaridade da vítima", c.v.escV],
      ["Escolaridade do agressor", c.v.escA],
      ["Ocupação do agressor", c.v.ocupA]
    ];
    const t = c.tipo==="consumado";
    return `<li class="case ${c.tipo}" id="c-${c.id}">
      <div class="when"><span class="d">${+d} ${MESES[+m-1]}</span><span class="m">${y}</span></div>
      <article class="card" aria-labelledby="h-${c.id}">
        <div class="card-head"><h3 id="h-${c.id}">${esc(c.titulo)}</h3><span class="badge ${t?"":"t"}">${t?"Feminicídio consumado":"Tentativa"}</span></div>
        <p class="where">${esc(c.onde)}</p>
        <p class="summary">${esc(c.resumo)}</p>
        <dl class="vars">${rows.map(([k,v])=>`<div><dt>${k}</dt><dd class="${isNI(v)?"ni":""}">${esc(isNI(v)?NI:v)}</dd></div>`).join("")}</dl>
        <p class="status"><strong>Situação:</strong> ${esc(c.status)}</p>
        ${c.nota?`<p class="sources">${esc(c.nota)}</p>`:""}
        <p class="sources">Fontes: ${c.fontes.map(f=>`<a href="${esc(f.u)}" target="_blank" rel="noopener">${esc(f.t)}</a>`).join("")}</p>
      </article></li>`;
  }).join("");
}

function bucketAge(a){
  if(isNI(a)) return NI;
  if(a<18) return "Menos de 18";
  if(a<30) return "18 a 29";
  if(a<40) return "30 a 39";
  if(a<50) return "40 a 49";
  if(a<60) return "50 a 59";
  return "60 ou mais";
}
const simplify = {
  meio: v => isNI(v)?NI : v.split(" (")[0],
  local: v => isNI(v)?NI : v,
  relacao: v => isNI(v)?NI : (/ex-/i.test(v) && !/\//.test(v) ? "Ex-parceiro (ex-marido, ex-namorado)" : /\//.test(v) ? "Parceiro ou ex-parceiro" : "Parceiro atual (marido, companheiro)"),
  filhos: v => isNI(v)?NI : v.startsWith("Sim") ? "Sim" : "Não",
  antecedentes: v => isNI(v)?NI : /Sem/i.test(v) ? "Sem antecedentes" : "Com antecedentes",
  esc: v => isNI(v)?NI : v.split(" (")[0]
};

function renderDist(){
  const list = visible();
  const groups = [
    ["Meio / arma", list.map(c=>simplify.meio(c.v.meio))],
    ["Relação com o agressor", list.map(c=>simplify.relacao(c.v.relacao))],
    ["Local do crime", list.map(c=>simplify.local(c.v.local))],
    ["Idade da vítima", list.map(c=>bucketAge(c.v.idadeV))],
    ["Idade do agressor", list.map(c=>bucketAge(c.v.idadeA))],
    ["Vítima tinha filhos", list.map(c=>simplify.filhos(c.v.filhos))],
    ["Antecedentes do agressor", list.map(c=>simplify.antecedentes(c.v.antecedentes))],
    ["Escolaridade da vítima", list.map(c=>simplify.esc(c.v.escV))],
    ["Escolaridade do agressor", list.map(c=>simplify.esc(c.v.escA))]
  ];
  const n = list.length || 1;
  document.getElementById("dist").innerHTML = groups.map(([title,vals])=>{
    const counts = d3.rollups(vals, v=>v.length, d=>d).sort((a,b)=> (a[0]===NI)-(b[0]===NI) || b[1]-a[1]);
    return `<div><h3>${title}</h3>${counts.map(([k,v])=>`<div class="bar ${k===NI?"ni":""}"><span class="lbl" title="${esc(k)}">${esc(k)}</span><span class="track"><span class="fill" style="width:${v/n*100}%;display:block"></span></span><span class="n">${v}</span></div>`).join("")}</div>`;
  }).join("");
}

function renderOutside(){
  document.getElementById("out").innerHTML = OUTSIDE.map(o=>`<li><b>${esc(o.q)}</b><span class="why">${esc(o.w)} <a href="${esc(o.u)}" target="_blank" rel="noopener">Fonte</a></span></li>`).join("");
}
