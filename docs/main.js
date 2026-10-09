// =====================================================================
// Início: liga os filtros e desenha tudo na primeira abertura.
// =====================================================================
function renderAll(){ renderTimeline(); renderDist(); drawPoints(); }

document.querySelectorAll(".filters button").forEach(b=>{
  b.addEventListener("click", ()=>{
    filter = b.dataset.f;
    document.querySelectorAll(".filters button").forEach(x=>x.setAttribute("aria-pressed", String(x===b)));
    renderAll();
  });
});

ajustarVB(); drawMap(); renderOutside(); renderAll(); svg.call(zoom.transform, frame(urbanBounds()));
