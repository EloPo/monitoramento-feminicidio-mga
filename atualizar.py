#!/usr/bin/env python3
"""
Atualização diária do Monitor de feminicídios em Maringá.

O que o script faz, em ordem:
  1. Busca notícias novas (Google Notícias + feeds de busca dos portais de Maringá + Lesfem).
  2. Descarta o que já foi analisado antes (dados/processados.json) e o que é anterior a out/2024.
  3. Lê o texto de cada notícia candidata.
  4. Classifica cada notícia:
       - com ANTHROPIC_API_KEY definida: o Claude lê a matéria, decide se o crime ocorreu DENTRO
         do município de Maringá, se é feminicídio consumado/tentado, e extrai as variáveis da pesquisa;
       - sem a chave: a notícia vai para dados/candidatos.json para revisão manual (nada é publicado).
  5. Atualiza dados/casos.json e dados/fora.json.
  6. Regrava docs/js/dados.js com os dados novos e a data da coleta (o resto do site não muda).
  7. Escreve um relatório em dados/ultimo_relatorio.md.

Uso:
  python atualizar.py              # coleta e atualiza
  python atualizar.py --so-gerar   # só regrava o site a partir dos JSON (depois de editar à mão)
  python atualizar.py --dias 30    # olha só notícias dos últimos 30 dias (padrão: desde out/2024)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "dados"
ARQ_DADOS_JS = RAIZ / "docs" / "dados.js"        # regravado a cada coleta
ARQ_GEO_JS = RAIZ / "docs" / "geo-maringa.js"     # loteamentos oficiais (só leitura)
ARQ_CASOS = DADOS / "casos.json"
ARQ_FORA = DADOS / "fora.json"
ARQ_PROCESSADOS = DADOS / "processados.json"
ARQ_CANDIDATOS = DADOS / "candidatos.json"
ARQ_RELATORIO = DADOS / "ultimo_relatorio.md"

INICIO_RECORTE = dt.date(2024, 10, 1)
NI = "Não informado"
MODELO = os.environ.get("MODELO_CLAUDE", "claude-sonnet-5-5")
UA = {"User-Agent": "Mozilla/5.0 (pesquisa academica; monitor de feminicidios Maringa)"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# ---------------------------------------------------------------- fontes
CONSULTAS_GOOGLE = [
    '"feminicídio" Maringá',
    '"tentativa de feminicídio" Maringá',
    'Maringá mulher morta companheiro',
    'Maringá mulher esfaqueada ex-companheiro',
    'Maringá mulher morta ex-marido',
    'Maringá "violência doméstica" mulher morta',
]
# Portais em WordPress aceitam busca em RSS: https://site/?s=termo&feed=rss2
PORTAIS_WP = [
    "maringapost.com.br", "gmconline.com.br", "omaringa.com.br", "andrealmenara.com.br",
    "cbnmaringa.com.br", "ofatomaringa.com", "maringamanchete.com.br", "maringamais.com.br", "g1.globo.com",
    "cnnbrasil.com.br", "cbn.globo.com", "gazetadopovo"
]
TERMOS_WP = ["feminicídio", "tentativa de feminicídio"]
LESFEM = "https://sites.uel.br/lesfem/memorial-de-vitimas-de-feminicidio-no-parana/memorial-de-vitimas-de-feminicidio-no-parana-{ano}/"

PALAVRAS = re.compile(
    r"feminic|morta pelo|morta a facadas|morta a tiros|matou a (?:mulher|esposa|companheira|ex)|"
    r"esfaque|ateou fogo|ateia fogo|esgan|estrangul|violência doméstica|maria da penha",
    re.I,
)


# ---------------------------------------------------------------- utilidades
def ler_json(p: Path, padrao):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return padrao


def gravar_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").upper().strip()


def data_por_extenso(d: dt.date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 1. coleta
def coletar(desde: dt.date) -> list[dict]:
    itens: dict[str, dict] = {}

    def add(titulo, link, resumo, data, origem):
        if not link:
            return
        if data and data < desde:
            return
        texto = f"{titulo} {resumo}"
        if not PALAVRAS.search(texto):
            return
        itens.setdefault(link, {"titulo": titulo.strip(), "url": link, "resumo": resumo.strip()[:600],
                                "data_pub": data.isoformat() if data else None, "origem": origem})

    def data_entry(e):
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                return dt.date(*e[k][:3])
        return None

    for q in CONSULTAS_GOOGLE:
        url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        try:
            feed = feedparser.parse(requests.get(url, headers=UA, timeout=30).content)
            for e in feed.entries:
                resumo = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ")
                add(e.get("title", ""), e.get("link"), resumo, data_entry(e), "Google Notícias")
        except Exception as ex:  # noqa: BLE001
            log(f"  aviso: Google Notícias falhou para {q!r}: {ex}")
        time.sleep(1)

    for site in PORTAIS_WP:
        for termo in TERMOS_WP:
            url = f"https://{site}/?s={quote_plus(termo)}&feed=rss2"
            try:
                r = requests.get(url, headers=UA, timeout=30)
                feed = feedparser.parse(r.content)
                for e in feed.entries:
                    resumo = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ")
                    add(e.get("title", ""), e.get("link"), resumo, data_entry(e), site)
            except Exception as ex:  # noqa: BLE001
                log(f"  aviso: {site} falhou: {ex}")
            time.sleep(1)

    # Lesfem: página do memorial do ano corrente (e do anterior em janeiro)
    hoje = dt.date.today()
    for ano in sorted({hoje.year, (hoje - dt.timedelta(days=31)).year}):
        url = LESFEM.format(ano=ano)
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.ok:
                soup = BeautifulSoup(r.text, "html.parser")
                for bloco in soup.find_all(["p", "li", "tr"]):
                    t = bloco.get_text(" ", strip=True)
                    if "maring" in t.lower() and len(t) > 30:
                        chave = f"{url}#{abs(hash(t)) % 10**10}"
                        itens.setdefault(chave, {"titulo": f"Lesfem — memorial {ano}", "url": chave,
                                                 "resumo": t[:1500], "data_pub": None, "origem": "Lesfem/UEL",
                                                 "texto_pronto": t})
        except Exception as ex:  # noqa: BLE001
            log(f"  aviso: Lesfem falhou: {ex}")
    return list(itens.values())


# ---------------------------------------------------------------- 3. leitura
def ler_materia(item: dict) -> tuple[str, str]:
    """Devolve (url_final, texto). Se não conseguir ler, usa título + resumo."""
    if item.get("texto_pronto"):
        return item["url"], item["texto_pronto"]
    try:
        r = requests.get(item["url"], headers=UA, timeout=30, allow_redirects=True)
        final = r.url
        if "news.google.com" in urlparse(final).netloc:
            return item["url"], f"{item['titulo']}\n{item['resumo']}"
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            t.decompose()
        corpo = soup.find("article") or soup
        paragrafos = [p.get_text(" ", strip=True) for p in corpo.find_all("p")]
        texto = "\n".join(p for p in paragrafos if len(p) > 40)
        return final, (f"{item['titulo']}\n{texto}")[:14000] or f"{item['titulo']}\n{item['resumo']}"
    except Exception:  # noqa: BLE001
        return item["url"], f"{item['titulo']}\n{item['resumo']}"


# ---------------------------------------------------------------- 4. classificação (Claude)
INSTRUCOES = """Você ajuda numa pesquisa acadêmica (TCC) que monitora feminicídios em Maringá (PR).
Leia a notícia e responda SOMENTE com um objeto JSON válido, sem texto antes ou depois.

Regras do recorte:
- Entra apenas feminicídio CONSUMADO ou TENTADO (tratado como feminicídio pela polícia, MP, Justiça ou Lesfem)
  cujo CRIME ocorreu DENTRO do município de Maringá, a partir de 01/10/2024.
- O local do crime é o que conta. Crimes em Sarandi, Paiçandu, Marialva, Mandaguaçu, Mandaguari, Nova Esperança
  ou qualquer outra cidade NÃO entram, mesmo que a manchete cite Maringá (ex.: suspeito preso em Maringá,
  vítima levada a hospital de Maringá, "região de Maringá").
- Se for um caso que já está na lista de casos existentes, trate como atualização.

Formato da resposta:
{
  "decisao": "novo" | "atualizacao" | "fora" | "irrelevante" | "duvida",
  "motivo": "frase curta explicando a decisão",
  "nome_agressor": "nome do agressor se aparecer na matéria, senão null (serve só para removê-lo do site)",
  "caso_existente_id": "id do caso existente, quando decisao = atualizacao",
  "atualizacao": {"status": "situação processual atualizada em 1-2 frases, ou null",
                  "variaveis": {"campo": "valor"}  // só campos que antes eram "Não informado" e a matéria informa
                 },
  "fora": {"quem_quando": "Nome da vítima (se consumado) ou 'Tentativa em <cidade>', DD/MM/AAAA",
           "por_que": "Crime em <cidade/bairro>. Fora do município." },   // quando decisao = fora e a matéria cita Maringá
  "novo": {
    "tipo": "consumado" | "tentado",
    "data": "AAAA-MM-DD (data do crime)",
    "nome_vitima": "nome completo se consumado; null se tentativa",
    "idade_vitima": número ou null,
    "onde": "descrição curta do local sem número da casa (ex.: 'Residência no Jardim Alvorada')",
    "bairro": "nome do bairro/loteamento como aparece na matéria, ou null",
    "resumo": "2 a 3 frases suas (paráfrase, não copie a matéria), SEM o nome do agressor",
    "status": "situação do suspeito/processo em 1-2 frases, SEM o nome do agressor",
    "v": {"idadeA": número ou null, "local": "...", "meio": "...", "filhos": "...", "antecedentes": "...",
          "relacao": "...", "escV": "...", "escA": "...", "ocupA": "..."}
  }
}
Nas variáveis use exatamente "Não informado" quando a matéria não trouxer o dado. Padrões:
- meio: "Arma branca (faca)", "Arma de fogo (...)", "Fogo (...)", "Asfixia/esganadura", "Agressão física (...)".
- relacao: "Companheiro", "Marido", "Ex-companheiro", "Ex-marido", "Ex-namorado", "Namorado", "Filho", etc.
- filhos: começar com "Sim - ..." ou "Não".
- antecedentes: "Sem antecedentes criminais" ou "Com antecedentes: ..." .
Nunca invente dados. Na dúvida sobre o local do crime ou sobre ser feminicídio, use "duvida".
"""


def classificar(cliente, item: dict, texto: str, casos: list[dict]) -> dict:
    existentes = [{"id": c["id"], "data": c["data"], "tipo": c["tipo"], "titulo": c["titulo"], "onde": c["onde"]}
                  for c in casos]
    msg = (f"Casos existentes: {json.dumps(existentes, ensure_ascii=False)}\n\n"
           f"Data de publicação: {item.get('data_pub')}\nFonte: {item.get('origem')}\nURL: {item['url']}\n\n"
           f"NOTÍCIA:\n{texto}")
    resp = cliente.messages.create(model=MODELO, max_tokens=2000, system=INSTRUCOES,
                                   messages=[{"role": "user", "content": msg}])
    bruto = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    m = re.search(r"\{.*\}", bruto, re.S)
    if not m:
        return {"decisao": "duvida", "motivo": "resposta sem JSON"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"decisao": "duvida", "motivo": "JSON inválido na resposta"}


# ---------------------------------------------------------------- 5. mapa (bairro -> ponto)
_BAIRROS = None


def carregar_bairros():
    global _BAIRROS
    if _BAIRROS is None:
        from shapely.geometry import shape
        texto = ARQ_GEO_JS.read_text(encoding="utf-8")
        inicio = texto.index("const MGA = ") + len("const MGA = ")
        mga = json.loads(texto[inicio:].strip().rstrip(";"))
        _BAIRROS = {}
        for f in mga["bairros"]["features"]:
            nome = f["properties"].get("n") or ""
            if not nome:
                continue
            g = shape(f["geometry"])
            atual = _BAIRROS.get(sem_acento(nome))
            if atual is None or g.area > atual[1].area:
                _BAIRROS[sem_acento(nome)] = (nome, g)
    return _BAIRROS


GENERICAS = {"JARDIM", "VILA", "CONJUNTO", "RESIDENCIAL", "HABITACIONAL", "PARQUE", "LOTEAMENTO", "BAIRRO",
             "CONDOMINIO", "CHACARAS", "DE", "DA", "DO", "DAS", "DOS", "E"}


def _base(nome: str) -> str:
    """Tira sufixos de partes/ampliações: 'JARDIM ALVORADA II PARTE' -> 'JARDIM ALVORADA'."""
    anterior = None
    while anterior != nome:
        anterior = nome
        nome = re.sub(r"\s*-?\s*(AMPLIACAO|\b[IVX]+\b|\b\d+\b|PARTE|\d+A PARTE|\d+ª PARTE)$", "", nome).strip()
    return nome


def localizar_bairro(texto: str | None):
    """Devolve (nome_para_exibir, [lon, lat], [nomes oficiais no mapa]) ou (None, None, []) se não houver correspondência segura."""
    if not texto:
        return None, None, []
    from shapely.ops import unary_union
    b = carregar_bairros()
    alvo = sem_acento(texto)
    alvo = re.sub(r"^BAIRRO\s+", "", alvo)
    alvo = re.sub(r"^CONJ\.?\s+", "CONJUNTO ", alvo)
    alvo = re.sub(r"^ZONA (\d)$", r"ZONA 0\1", alvo)
    escolhidos = []
    if alvo in b:                                   # 1. nome idêntico
        escolhidos = [alvo]
    if not escolhidos:                              # 2. mesmo loteamento dividido em partes
        escolhidos = [k for k in b if _base(k) == alvo]
    if not escolhidos:                              # 3. todas as palavras-chave batem, com o mínimo de sobras
        chaves = set(alvo.split()) - GENERICAS
        if chaves:
            cands = [(len(set(k.split()) - GENERICAS - chaves), k) for k in b if chaves <= set(k.split())]
            if cands:
                menor = min(c[0] for c in cands)
                melhores = [k for n, k in cands if n == menor]
                if menor <= 1 and len({_base(k) for k in melhores}) == 1:
                    escolhidos = melhores
    if not escolhidos:
        return None, None, []
    nome = _base(b[escolhidos[0]][0]) if len(escolhidos) > 1 else b[escolhidos[0]][0]
    g = unary_union([b[k][1].buffer(0) for k in escolhidos])
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda x: x.area)
    p = g.representative_point()
    return nome, [round(p.x, 5), round(p.y, 5)], [b[k][0] for k in escolhidos]


# ---------------------------------------------------------------- privacidade
def limpar_nome(obj, nome):
    """Remove o nome do agressor de qualquer texto do caso."""
    if not nome:
        return obj
    partes = [nome] + [p for p in nome.split() if len(p) > 3]
    if isinstance(obj, str):
        for p in partes:
            obj = re.sub(re.escape(p), "o suspeito" if p == nome else "", obj, flags=re.I)
        obj = re.sub(r"\s{2,}", " ", obj).strip()
        return re.sub(r"(^|[.!?]\s+)o suspeito", lambda m: m.group(1) + "O suspeito", obj)
    if isinstance(obj, dict):
        return {k: limpar_nome(v, nome) for k, v in obj.items()}
    if isinstance(obj, list):
        return [limpar_nome(v, nome) for v in obj]
    return obj


def nome_fonte(url: str, origem: str) -> str:
    host = urlparse(url).netloc.replace("www.", "")
    return origem if origem and "." not in origem and origem != "Google Notícias" else host


# ---------------------------------------------------------------- 6. site
def gerar_site(casos, fora, data: dt.date):
    """Regrava docs/dados.js. HTML, CSS e o restante do JS ficam intactos."""
    ARQ_DADOS_JS.write_text(
        "// ARQUIVO GERADO PELO atualizar.py a partir de dados/casos.json e dados/fora.json.\n"
        "// Não edite aqui: edite os JSON e rode  python atualizar.py --so-gerar\n"
        f"const UPDATED = {json.dumps(data_por_extenso(data), ensure_ascii=False)};\n"
        f"const CASES = {json.dumps(casos, ensure_ascii=False, indent=1)};\n"
        f"const OUTSIDE = {json.dumps(fora, ensure_ascii=False, indent=1)};\n",
        encoding="utf-8")


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-gerar", action="store_true", help="só regrava o site a partir dos JSON")
    ap.add_argument("--dias", type=int, default=None, help="olhar só notícias dos últimos N dias")
    args = ap.parse_args()

    hoje = dt.date.today()
    casos = ler_json(ARQ_CASOS, [])
    fora = ler_json(ARQ_FORA, [])

    if args.so_gerar:
        gerar_site(casos, fora, hoje)
        log("Site regravado a partir dos JSON.")
        return

    processados = ler_json(ARQ_PROCESSADOS, {})
    candidatos = ler_json(ARQ_CANDIDATOS, [])
    desde = max(INICIO_RECORTE, hoje - dt.timedelta(days=args.dias)) if args.dias else INICIO_RECORTE

    log(f"Coletando notícias desde {desde:%d/%m/%Y}…")
    itens = [i for i in coletar(desde) if i["url"] not in processados]
    log(f"{len(itens)} notícias novas para analisar.")

    chave = os.environ.get("ANTHROPIC_API_KEY")
    cliente = None
    if chave:
        import anthropic
        cliente = anthropic.Anthropic(api_key=chave)
    else:
        log("ANTHROPIC_API_KEY não definida: as notícias vão para dados/candidatos.json para revisão manual.")

    rel = {"novos": [], "atualizados": [], "fora": [], "duvidas": [], "erros": []}
    urls_existentes = {f["u"] for c in casos for f in c.get("fontes", [])}

    for it in itens:
        url, texto = ler_materia(it)
        if url in urls_existentes:
            processados[it["url"]] = {"em": hoje.isoformat(), "decisao": "ja_usada"}
            continue
        if not cliente:
            candidatos.append({**it, "url_final": url})
            processados[it["url"]] = {"em": hoje.isoformat(), "decisao": "revisao_manual"}
            continue
        try:
            r = classificar(cliente, it, texto, casos)
        except Exception as ex:  # noqa: BLE001  (não marca como processada: tenta de novo amanhã)
            rel["erros"].append(f"{it['titulo']} — {ex}")
            continue

        dec = r.get("decisao")
        r = limpar_nome(r, r.get("nome_agressor"))
        fonte = {"t": nome_fonte(url, it.get("origem", "")), "u": url}

        if dec == "novo" and r.get("novo"):
            n = r["novo"]
            try:
                data_crime = dt.date.fromisoformat(n["data"])
            except Exception:  # noqa: BLE001
                data_crime = None
            if not data_crime or data_crime < INICIO_RECORTE:
                rel["duvidas"].append(f"{it['titulo']} — data do crime ausente ou anterior a out/2024 ({url})")
            else:
                bairro, coords, oficiais = localizar_bairro(n.get("bairro"))
                v = {k: (n.get("v", {}).get(k) or NI) for k in
                     ["local", "meio", "filhos", "antecedentes", "relacao", "escV", "escA", "ocupA"]}
                v["idadeV"] = n.get("idade_vitima")
                v["idadeA"] = n.get("v", {}).get("idadeA")
                if n["tipo"] == "consumado" and n.get("nome_vitima"):
                    titulo = n["nome_vitima"]
                else:  # sobrevivente nunca é identificada
                    titulo = f"Mulher, {v['idadeV']} anos" if v["idadeV"] else "Mulher (idade não informada)"
                caso = {
                    "id": f"{n['tipo'][:1]}{data_crime:%Y%m%d}{len(casos)}",
                    "tipo": n["tipo"], "data": data_crime.isoformat(), "titulo": titulo,
                    "onde": n.get("onde") or NI, "bairro": bairro, "coords": coords,
                    "resumo": n.get("resumo", ""), "v": v, "status": n.get("status") or NI,
                    "fontes": [fonte],
                }
                if len(oficiais) > 1:
                    caso["bairros_mapa"] = oficiais
                if n.get("bairro") and not bairro:
                    caso["nota"] = f"Bairro informado pela imprensa ({n['bairro']}) não encontrado na base oficial; caso fora do mapa."
                casos.append(caso)
                urls_existentes.add(url)
                rel["novos"].append(f"{caso['data']} · {caso['titulo']} ({caso['tipo']}) — {url}")

        elif dec == "atualizacao" and r.get("caso_existente_id"):
            c = next((c for c in casos if c["id"] == r["caso_existente_id"]), None)
            if c:
                a = r.get("atualizacao") or {}
                if a.get("status"):
                    c["status"] = a["status"]
                for k, val in (a.get("variaveis") or {}).items():
                    if k in c["v"] and c["v"][k] in (None, NI) and val not in (None, NI):
                        c["v"][k] = val
                if url not in {f["u"] for f in c["fontes"]}:
                    c["fontes"].insert(0, fonte)
                urls_existentes.add(url)
                rel["atualizados"].append(f"{c['titulo']} — {r.get('motivo', '')}")

        elif dec == "fora" and r.get("fora"):
            f = r["fora"]
            if f.get("quem_quando") and all(o["u"] != url for o in fora) \
                    and sem_acento(f["quem_quando"]) not in {sem_acento(o["q"]) for o in fora}:
                fora.insert(0, {"q": f["quem_quando"], "w": f.get("por_que", ""), "u": url})
                rel["fora"].append(f"{f['quem_quando']} — {f.get('por_que', '')}")

        elif dec == "duvida":
            candidatos.append({**it, "url_final": url, "motivo": r.get("motivo")})
            rel["duvidas"].append(f"{it['titulo']} — {r.get('motivo', '')} ({url})")

        processados[it["url"]] = {"em": hoje.isoformat(), "decisao": dec}
        time.sleep(0.5)

    casos.sort(key=lambda c: c["data"], reverse=True)
    gravar_json(ARQ_CASOS, casos)
    gravar_json(ARQ_FORA, fora)
    gravar_json(ARQ_PROCESSADOS, processados)
    gravar_json(ARQ_CANDIDATOS, candidatos)
    gerar_site(casos, fora, hoje)

    linhas = [f"# Coleta de {data_por_extenso(hoje)}", "",
              f"Notícias analisadas: {len(itens)}", ""]
    for titulo, chave_rel in [("Casos novos incluídos", "novos"), ("Casos atualizados", "atualizados"),
                              ("Descartados por serem de fora de Maringá", "fora"),
                              ("Para você conferir", "duvidas"), ("Erros (serão tentados de novo)", "erros")]:
        linhas.append(f"## {titulo}")
        linhas += [f"- {x}" for x in rel[chave_rel]] or ["- nenhum"]
        linhas.append("")
    ARQ_RELATORIO.write_text("\n".join(linhas), encoding="utf-8")
    log("\n".join(linhas))


if __name__ == "__main__":
    main()
