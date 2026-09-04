# Tramitação do Regimento Interno — Parque dos Cedros

Site estático (sem custo, hospedado no GitHub Pages) para acompanhar a
tramitação do Regimento Interno: texto-base, e as emendas e pareceres
técnicos apresentados pelos condôminos.

## Estrutura do repositório

```
.
├── index.html                 → página inicial (Apresentação)
├── texto-base.html            → texto-base do Regimento, navegável
├── emendas.html                → emendas e pareceres, por tipo ou por unidade
├── data/
│   └── emendas.json            → dados já mesclados das 2 planilhas (gerado automaticamente)
├── scripts/
│   └── atualizar_emendas.py    → script que busca as planilhas e gera o emendas.json
└── .github/workflows/
    └── atualizar-emendas.yml   → roda o script sozinho, periodicamente
```

**Você não precisa editar `data/emendas.json` nem rodar o script manualmente.**
Isso acontece sozinho — veja "Como a atualização automática funciona" abaixo.

## Como publicar (GitHub Pages)

1. Crie uma conta em [github.com](https://github.com), se ainda não tiver.
2. Crie um repositório novo (pode ser público — necessário para o GitHub
   Pages gratuito).
3. Suba **todos** os arquivos e pastas deste pacote para a raiz do
   repositório, mantendo a estrutura de pastas acima (incluindo a pasta
   `.github`, que costuma ficar oculta — confirme que ela foi enviada).
4. Vá em **Settings → Pages**, e em "Source" escolha a branch `main` e a
   pasta `/ (root)`. Salve.
5. Vá na aba **Actions** do repositório. Se aparecer um aviso pedindo para
   habilitar os workflows, clique para habilitar.
6. Ainda na aba Actions, clique no workflow **"Atualizar emendas"** → botão
   **"Run workflow"** → Run workflow. Isso roda a busca das planilhas pela
   primeira vez, sem precisar esperar o horário programado — assim o site já
   nasce com as emendas atuais, em vez do arquivo vazio.
7. Em alguns minutos, o site estará no ar em
   `https://SEU-USUARIO.github.io/NOME-DO-REPOSITORIO/`.

## Como a atualização automática funciona

O arquivo `.github/workflows/atualizar-emendas.yml` roda o script
`scripts/atualizar_emendas.py` **a cada 15 minutos**, automaticamente, dentro
da infraestrutura do próprio GitHub (de graça, dentro da cota gratuita de
Actions). O script:

1. Busca as duas planilhas publicadas como CSV;
2. Identifica o tipo de cada manifestação (aditiva, modificativa, supressiva,
   substitutiva, redação ou parecer técnico) e organiza os campos;
3. Mescla os registros das duas fontes, ordena por data de envio e grava tudo
   em `data/emendas.json`;
4. Se algo mudou desde a última vez, o próprio Action confirma (commit) e
   publica (push) o arquivo atualizado no repositório.

O site (`emendas.html`) só lê esse `data/emendas.json` — nunca fala
diretamente com o Google Sheets pelo navegador. Isso evita um problema real
de CORS (bloqueio de segurança do navegador) que ocorre ao tentar buscar uma
planilha do Google direto do JavaScript da página, mesmo publicada como CSV.

### Ajustar a frequência de atualização

Edite a linha `cron` em `.github/workflows/atualizar-emendas.yml`. Exemplos:
- `*/15 * * * *` → a cada 15 minutos (padrão)
- `*/30 * * * *` → a cada 30 minutos
- `0 * * * *` → uma vez por hora

Use [crontab.guru](https://crontab.guru) para conferir qualquer expressão.

### Forçar uma atualização imediata

Aba **Actions** → workflow **"Atualizar emendas"** → **"Run workflow"**.
Útil, por exemplo, pouco antes de divulgar o link para os condôminos.

## Links reais já configurados

- Formulário de manifestações (menu superior e página inicial)
- Texto-base em PDF (na página de texto-base)

Se algum desses links mudar no futuro, é só substituir a URL correspondente
nos arquivos `.html` (busca por `docs.google.com/forms` ou
`drive.google.com`).

## Sobre a visibilidade das planilhas

As duas planilhas estão publicadas via "Publicar na Web" do Google Sheets,
o que as torna acessíveis a qualquer pessoa com o link — mesmo que a
planilha, nas configurações normais de compartilhamento, continue restrita.
Isso é intencional aqui (o objetivo é dar transparência às emendas), mas
vale ter em mente.
