# HQGen

Renderiza o JSON de uma história (MakeStory) em páginas de quadrinho PNG. Cada cena vira um painel com a imagem, narração e balões. A API sobe os PNGs para S3 ou R2 e devolve as URLs.

Há dois jeitos de usar: a linha de comando grava arquivos locais; a API FastAPI faz o mesmo render e envia para o bucket.

## Como funciona

```
JSON da história
  → parser (scenes, narrations, dialogues, image)
  → baixa a imagem da cena (URL ou caminho local)
  → posiciona legendas e balões (MediaPipe evita o rosto)
  → PNG de página, ou um PNG por cena
  → disco (CLI) ou bucket (API)
```

A imagem da cena só entra se `image.image_status` for `generated` e houver `image_url`.

## Estrutura do projeto

```
.
├── main.py        # CLI
├── api.py         # FastAPI
├── parser.py      # JSON → cenas
├── renderer.py    # Páginas e cenas
├── panels.py      # Monta cada painel
├── placement.py   # Onde cabe o texto
├── faces.py       # Detecção de rosto (MediaPipe)
├── text.py        # Balões, legendas, fontes
├── layout.py      # Webtoon e página clássica
├── storage.py     # Upload boto3
├── config.py      # Settings do bucket
├── fonts/         # Bangers e Comic Neue
└── requirements.txt
```

## Pré-requisitos

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

A CLI não precisa de bucket. A API precisa das variáveis da seção abaixo. Não commite o `.env`.

## CLI

```bash
python main.py historia.json
python main.py historia.json --scene-images --output-dir output
python main.py historia.json --mode classic --light
```

Sem `--output-dir`, páginas vão para `output/`. Com `--scene-images`, cada cena vai para `<output-dir>/<story_id>/`.

| Flag | Default | Efeito |
|------|---------|--------|
| `--mode` | `webtoon` | `webtoon` (faixa vertical) ou `classic` |
| `--width` | `800` | Largura da página |
| `--panel-height` | `980` | Altura de um painel |
| `--page-height` | `1200` | Altura da página clássica |
| `--panels-per-page` | `4` | 2, 3 ou 4 painéis no modo clássico |
| `--scene-images` | off | Um PNG por cena, sem empilhar páginas |
| `--light` | off | Fundo claro |
| `--disable-face-detection` | off | Não desvia o texto do rosto |
| `--debug-faces` | off | Desenha as caixas dos rostos |

## API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

| Rota | Descrição |
|------|-----------|
| `GET /health` | `{"status": "ok"}` |
| `POST /render` | Empilha painéis em páginas. No webtoon isso costuma ser uma imagem alta |
| `POST /render/scenes` | Um PNG por cena |

### Request

```json
{
  "story": {
    "id": "6",
    "scenes": [
      {
        "id": 1,
        "narrations": [{ "content": "A rua estava vazia." }],
        "dialogues": [{ "character": "Ana", "content": "Espera." }],
        "image": {
          "image_url": "https://example.com/cena.png",
          "image_status": "generated"
        }
      }
    ]
  },
  "options": {
    "layout_mode": "webtoon",
    "theme_dark": true
  }
}
```

`options` é opcional. Os campos espelham `RenderOptions` em `models.py` (`page_width`, `panel_height`, `classic_panels_per_page`, razões de largura dos balões, etc.).

### Response

```json
{
  "story_id": "6",
  "mode": "scenes",
  "files": [
    {
      "filename": "scene_001_id_1.png",
      "key": "generated-stories/6/scene_001_id_1.png",
      "bucket": "meu-bucket",
      "content_type": "image/png",
      "url": "https://..."
    }
  ]
}
```

Sem cenas renderizáveis a API responde `422`. Falha de credencial ou de upload responde `500` ou `502`.

## Variáveis de ambiente

Obrigatória para a API: um nome de bucket entre `AWS_BUCKET`, `AWS_BUCKET_NAME`, `AWS_S3_BUCKET`, `S3_BUCKET` ou `S3_BUCKET_NAME`.

| Variável | Default | Uso |
|----------|---------|-----|
| `AWS_BUCKET` | — | Bucket de destino |
| `AWS_DEFAULT_REGION` | — | Região. Alias: `AWS_REGION`, `S3_REGION` |
| `AWS_ENDPOINT` | — | Endpoint S3-compatível (R2). Alias: `AWS_ENDPOINT_URL` |
| `AWS_URL` | — | Base pública das URLs devolvidas |
| `AWS_ACCESS_KEY_ID` | — | Access key |
| `AWS_SECRET_ACCESS_KEY` | — | Secret |
| `AWS_USE_PATH_STYLE_ENDPOINT` | `false` | Path-style no endpoint |
| `S3_PREFIX` | `generated-stories` | Prefixo das chaves |
| `S3_RETURN_PRESIGNED_URLS` | `false` | Devolve URL assinada em vez da URL pública |
| `S3_PRESIGNED_EXPIRATION_SECONDS` | `3600` | Validade da URL assinada |
| `S3_ACL` | — | ACL do objeto, se o bucket exigir |
