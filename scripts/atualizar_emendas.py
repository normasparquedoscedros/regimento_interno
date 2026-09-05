#!/usr/bin/env python3
"""
Busca as duas planilhas do Google Forms (publicadas como CSV), mescla os
registros e grava data/emendas.json — arquivo que o site (emendas.html) lê.

Cada registro traz TODOS os campos preenchidos no formulário (obrigatórios
ou não) para aquele tipo de manifestação, em texto integral (sem corte),
organizados em uma lista "campos" na ordem em que devem ser exibidos.

Roda dentro do GitHub Actions (lado do servidor), onde não existe restrição
de CORS, evitando o problema que ocorre ao buscar direto do navegador.
"""

import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---- Fontes de dados (planilhas publicadas como CSV) ----
FONTES = [
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSNC5MLWZBXWqUmajfZl-FBGuY1rXJmyDOhI8WCrsotZnXrWIr0rFJdk1CljM6COGZr4i4Q3CWGsAO1/pub?gid=1142313163&single=true&output=csv",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vR6P2C0wX-jhWltp1fdDM88YiKh_cKWKATnpUhqG74uF-qmVZ61Hyht2lXr5gXCKTqgoKv2ID2NVKGl/pub?gid=1129295832&single=true&output=csv",
]

SAIDA = Path(__file__).resolve().parent.parent / "data" / "emendas.json"

# Para cada tipo, os campos que existem no formulário, na ordem em que
# devem aparecer no "inteiro teor", com (rótulo exibido, coluna).
# O rótulo é o que a pessoa vê; a coluna é o índice na planilha (0-based).
CAMPOS_POR_TIPO = {
    "redacao": [
        ("Item do texto-base", 6),
        ("Texto atual", 7),
        ("Nova redação proposta", 8),
        ("Justificativa", 9),
    ],
    "aditiva": [
        ("Onde inserir (dispositivo de referência)", 12),
        ("Texto a ser incluído", 13),
        ("Justificativa", 14),
    ],
    "modificativa": [
        ("Item do texto-base", 20),
        ("Texto atual", 21),
        ("Novo texto proposto", 22),
        ("Justificativa", 23),
    ],
    "supressiva": [
        ("Item do texto-base", 16),
        ("Texto a suprimir", 17),
        ("Justificativa", 18),
    ],
    "substitutiva": [
        ("Item do texto-base", 25),
        ("Justificativa", 27),
        # o texto da emenda em si vem só pelo PDF anexado (ver campo "pdf")
    ],
    "parecer": [
        ("Item/tema do parecer", 29),
        ("Especialidade", 30),
        ("Observações", 32),
        # o parecer em si vem só pelo PDF anexado (ver campo "pdf")
    ],
}

# Coluna do PDF anexado, por tipo (quando existir)
PDF_POR_TIPO = {
    "substitutiva": 26,
    "parecer": 31,
}

# Qual campo (rótulo) usar como "título" resumido na listagem
TITULO_POR_TIPO = {
    "redacao": "Item do texto-base",
    "aditiva": "Onde inserir (dispositivo de referência)",
    "modificativa": "Item do texto-base",
    "supressiva": "Item do texto-base",
    "substitutiva": "Item do texto-base",
    "parecer": "Item/tema do parecer",
}


def buscar_csv(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig")  # utf-8-sig remove BOM se houver
    return list(csv.reader(io.StringIO(raw)))


def txt(v) -> str:
    return (v or "").strip()


def truncar(s: str, n: int) -> str:
    s = txt(s)
    return s[: n].strip() + "…" if len(s) > n else s


def parse_timestamp(ts: str):
    try:
        return datetime.strptime(txt(ts), "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return datetime.min


def mapear_linha(cols: list[str]):
    if not cols or len(cols) < 12:
        return None

    def c(i):
        return cols[i] if i < len(cols) else ""

    nome = txt(c(1))
    unidade = txt(c(2))
    tipo_raw = txt(c(5)).lower()
    if not nome or not unidade or not tipo_raw:
        return None

    if tipo_raw.startswith("emenda de mérito"):
        grupo = "merito"
    elif tipo_raw.startswith("emenda de redação"):
        grupo = "redacao"
    elif tipo_raw.startswith("parecer técnico"):
        grupo = "parecer"
    else:
        return None

    if grupo == "redacao":
        tipo = "redacao"
    elif grupo == "parecer":
        tipo = "parecer"
    else:
        nat = txt(c(11)).lower()
        if nat.startswith("emenda aditiva"):
            tipo = "aditiva"
        elif nat.startswith("emenda modificativa"):
            tipo = "modificativa"
        elif nat.startswith("emenda supressiva"):
            tipo = "supressiva"
        elif nat.startswith("emenda substitutiva"):
            tipo = "substitutiva"
        else:
            return None

    # Monta TODOS os campos deste tipo, em texto integral (sem truncar)
    campos = []
    for definicao in CAMPOS_POR_TIPO[tipo]:
        if len(definicao) == 2:
            rotulo, col = definicao
            valor = txt(c(col))
        else:
            rotulo, col_principal, col_alt = definicao
            valor = txt(c(col_principal)) or txt(c(col_alt))
        campos.append({"rotulo": rotulo, "valor": valor})

    pdf = None
    if tipo in PDF_POR_TIPO:
        pdf = txt(c(PDF_POR_TIPO[tipo])) or None

    # Título resumido (para a listagem), truncado só para não estourar o layout;
    # o conteúdo completo continua disponível em "campos" (sem corte).
    rotulo_titulo = TITULO_POR_TIPO[tipo]
    valor_titulo = next((cp["valor"] for cp in campos if cp["rotulo"] == rotulo_titulo), "")
    titulo = truncar(valor_titulo, 140) or "(item não informado)"

    return {
        "tipo": tipo,
        "unidade": unidade,
        "nome": nome,
        "titulo": titulo,
        "campos": campos,
        "pdf": pdf,
        "timestamp": txt(c(0)),
    }


def main():
    todos = []
    erros = []
    for url in FONTES:
        try:
            linhas = buscar_csv(url)
        except Exception as e:  # nunca deixa o job quebrar por causa de 1 fonte
            print(f"AVISO: falha ao buscar {url}: {e}", file=sys.stderr)
            erros.append(str(e))
            continue
        for linha in linhas[1:]:  # pula cabeçalho
            rec = mapear_linha(linha)
            if rec:
                todos.append(rec)

    todos.sort(key=lambda r: parse_timestamp(r["timestamp"]))

    cont_em = cont_pt = 0
    for r in todos:
        if r["tipo"] == "parecer":
            cont_pt += 1
            r["id"] = f"PT-{cont_pt:03d}"
        else:
            cont_em += 1
            r["id"] = f"EM-{cont_em:03d}"

    saida = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(todos),
        "erros": erros,
        "registros": todos,
    }

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(todos)} registros gravados em {SAIDA}")

    if not todos and erros:
        # Se as duas fontes falharam e não há nenhum registro, sinaliza erro
        # para o workflow (mas o JSON antigo já commitado no repo continua no ar).
        sys.exit(1)


if __name__ == "__main__":
    main()
