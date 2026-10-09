# Monitor de feminicídios em Maringá — atualização automática

Este pacote atualiza o site todos os dias, sozinho, com notícias de feminicídio consumado ou tentado
ocorrido **dentro do município de Maringá**, de 1º de outubro de 2024 até a data da coleta.


**Onde mexer para cada tipo de mudança:**

| Quero mudar… | Arquivo |
|---|---|
| Cores, fontes, tamanhos | `docs/css/estilo.css` (as cores estão todas no bloco `:root`, no topo) |
| Títulos, textos fixos, telefones de ajuda | `docs/index.html` |
| Um caso, uma variável, uma fonte | `dados/casos.json`, depois `python atualizar.py --so-gerar` |
| Como as variáveis são agrupadas nas barras | `docs/js/pagina.js` (funções `bucketAge` e `simplify`) |
| Aparência ou comportamento do mapa | `docs/js/mapa.js` |

O `docs/js/dados.js` é sempre regravado pelo script, então não edite esse arquivo diretamente:
qualquer mudança feita nele some na coleta seguinte. A coleta automática nunca altera o HTML, o CSS
nem os outros arquivos JS.

## Como o script decide o que entra

1. Busca no Google Notícias e na busca dos portais de Maringá (Maringá Post, GMC Online, O Maringá,
   André Almenara, CBN Maringá, O Fato, Maringá Manchete, Maringá Mais), além do Memorial do Lesfem/UEL.
2. Lê cada matéria nova e envia o texto para o Claude (API da Anthropic), que decide:
   - se é feminicídio consumado ou tentado;
   - se o **crime aconteceu dentro de Maringá** (casos de Sarandi, Paiçandu etc. vão para "fora");
   - se é um caso novo ou o andamento de um caso que já está no site;
   - e extrai as variáveis: idades, local, meio/arma, filhos, antecedentes, relação, escolaridade, ocupação.
3. O próprio script garante a privacidade: sobreviventes de tentativa nunca são nomeadas
   e o nome do agressor é apagado de todos os textos.
4. O bairro informado é localizado na base oficial de loteamentos da Prefeitura. Se não houver
   correspondência segura, o caso aparece só na linha do tempo, com uma nota.
5. Regrava `docs/js/dados.js` e escreve o relatório.

Quando o Claude fica em dúvida (local incerto, não está claro se é feminicídio), a notícia vai para
`dados/candidatos.json` e para a seção "Para você conferir" do relatório. Nada duvidoso é publicado.

## Opção A — rodar sozinho todo dia no GitHub (recomendado, grátis)

1. Crie uma conta em https://github.com e um repositório novo (pode ser público).
2. Envie todos os arquivos desta pasta para o repositório (botão **Add file → Upload files**;
   a pasta `.github` também precisa ir).
3. Crie uma chave da API em https://console.anthropic.com (é paga por uso; o custo por dia é baixo,
   porque o script só analisa notícias novas).
4. No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
   Nome: `ANTHROPIC_API_KEY`. Valor: a chave.
5. **Settings → Pages**: em "Branch" escolha `main` e a pasta `/docs`. Salve.
   O endereço do site aparece ali (algo como `https://seu-usuario.github.io/nome-do-repositorio/`).
6. **Actions → Atualizar monitor → Run workflow** para rodar a primeira vez. A primeira coleta
   olha todas as notícias desde out/2024 e demora mais; as seguintes são rápidas.

A partir daí roda todo dia às 6h50. O resultado de cada dia aparece na aba **Actions**, e o relatório
fica em `dados/ultimo_relatorio.md`.

## Opção B — rodar no seu computador

```bash
pip install -r requirements.txt
# Windows (PowerShell):  $env:ANTHROPIC_API_KEY="sua-chave"
# Mac/Linux:             export ANTHROPIC_API_KEY="sua-chave"
python atualizar.py
```

Depois abra `docs/index.html` no navegador (dois cliques; funciona sem servidor, mas precisa de internet para carregar a biblioteca do mapa e as fontes). Para rodar todo dia, use o Agendador de Tarefas do Windows
(ou `cron` no Mac/Linux) apontando para `python atualizar.py` nesta pasta.

**Sem a chave da API** o script ainda coleta as notícias, mas não decide nada sozinho: ele lista
as candidatas em `dados/candidatos.json` para você revisar e incluir à mão.

## Corrigir ou incluir um caso à mão

Edite `dados/casos.json` (ou `dados/fora.json`) e rode:

```bash
python atualizar.py --so-gerar
```

Isso só regrava o site a partir dos arquivos, sem buscar notícias. No GitHub, basta editar o arquivo
pelo site e esperar a coleta do dia seguinte, ou rodar o workflow.

## Limites

- O script depende de a notícia ser publicada. Tentativas pouco noticiadas podem não aparecer.
- Escolaridade e antecedentes raramente aparecem na imprensa; ficam como "Não informado".
- A classificação é automática. Confira o relatório de vez em quando, principalmente a seção
  "Para você conferir", antes de usar os números no TCC.
