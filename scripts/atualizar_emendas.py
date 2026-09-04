#!/usr/bin/env python3
"""
Busca as duas planilhas do Google Forms (publicadas como CSV), mescla os
registros e grava data/emendas.json — arquivo que o site (emendas.html) lê.

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


def buscar_csv(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig")  # utf-8-sig remove BOM se houver
    return list(csv.reader(io.StringIO(raw)))


def txt(v) -> str:
    return (v or "").strip()


def truncar(s: str, n: int) -> str:
    s = txt(s)
    return s[:n].strip() + "…" if len(s) > n else s


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

    pdf = None
    if grupo == "redacao":
        tipo = "redacao"
        item = txt(c(6))
        texto_principal = txt(c(8)) or txt(c(7))
        justificativa = txt(c(9))
    elif grupo == "parecer":
        tipo = "parecer"
        item = txt(c(29))
        texto_principal = txt(c(30))
        justificativa = txt(c(32))
        pdf = txt(c(31)) or None
    else:
        nat = txt(c(11)).lower()
        if nat.startswith("emenda aditiva"):
            tipo = "aditiva"
            item, texto_principal, justificativa = txt(c(12)), txt(c(13)), txt(c(14))
        elif nat.startswith("emenda modificativa"):
            tipo = "modificativa"
            item, texto_principal, justificativa = txt(c(20)), txt(c(22)), txt(c(23))
        elif nat.startswith("emenda supressiva"):
            tipo = "supressiva"
            item, texto_principal, justificativa = txt(c(16)), txt(c(17)), txt(c(18))
        elif nat.startswith("emenda substitutiva"):
            tipo = "substitutiva"
            item, texto_principal, justificativa = txt(c(25)), txt(c(27)), txt(c(27))
            pdf = txt(c(26)) or None
        else:
            return None

    return {
        "tipo": tipo,
        "unidade": unidade,
        "nome": nome,
        "art": truncar(item, 110) or "—",
        "excerto": truncar(texto_principal or justificativa, 260) or "(sem descrição preenchida)",
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
