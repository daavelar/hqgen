Crie um sistema em Python para gerar páginas de HQ (histórias em quadrinhos) a partir do formato de dados da MakeStory AI.

O sistema deve consumir diretamente um JSON no formato da API (contendo story, items e scenes) e gerar uma ou mais páginas de HQ como imagens PNG.

---

## 🎯 Objetivo

Transformar automaticamente a estrutura narrativa em páginas visuais de HQ.

Cada scene deve virar um painel (quadro), contendo:

* imagem (se disponível)
* narração
* diálogos

---

## 📥 Entrada

O sistema deve aceitar o JSON completo da API MakeStory, incluindo:

* story
* items
* scenes

Deve priorizar o uso de:

* scenes[].narrations
* scenes[].dialogues
* scenes[].image

---

## 🧩 Regras de transformação

### 1. Cada scene = 1 painel

Para cada scene:

* Se image.image_url existir e status = "generated":
  → carregar e usar a imagem

* Se não existir:
  → gerar placeholder (fundo escuro com texto "Imagem não disponível")

---

### 2. Layout da página

O sistema deve suportar 2 modos:

#### Modo A (padrão): Webtoon vertical

* painéis empilhados verticalmente
* largura fixa (ex: 800px)
* altura dinâmica

#### Modo B: Página HQ clássica

* grid automático (2 ou 3 painéis por página)

---

### 3. Renderização de texto

#### Narração:

* caixa retangular no topo do painel
* fundo semi-transparente escuro
* texto branco

#### Diálogo:

* renderizar como balões simples:

  * fundo branco
  * texto preto
  * bordas arredondadas
* incluir nome do personagem antes da fala

---

### 4. Ordem dos elementos

Dentro de cada painel:

1. imagem de fundo
2. narração (topo)
3. diálogos (parte inferior ou distribuídos)

---

### 5. Tipografia

* usar fonte estilo HQ (ou fallback padrão)
* implementar quebra automática de linha
* respeitar margens internas (padding)

---

## 🧠 Processamento

Criar uma função:

render_story_to_pages(story_json: dict) -> List[Image]

Passos internos:

1. Iterar sobre scenes
2. Para cada scene:

   * extrair narrations
   * extrair dialogues
   * extrair imagem
3. Gerar painel
4. Montar página(s)

---

## 🧱 Estrutura do código

Separar em módulos:

* parser.py → interpreta o JSON da MakeStory
* layout.py → define posições dos painéis
* renderer.py → desenha imagem final
* text.py → quebra de linha e renderização
* panels.py → criação de cada painel

---

## 📤 Saída

* salvar imagens como:

  * page_1.png
  * page_2.png
* alta qualidade

---

## ⚠️ Regras importantes

* ignorar items[] (usar apenas scenes, pois já estão agrupadas)
* suportar cenas sem imagem
* suportar múltiplas páginas automaticamente

---

## 🚀 Extras (importante)

Se possível, implementar:

* fallback visual bonito para imagens ausentes
* padding consistente entre painéis
* bordas suaves nos quadros
* opção de tema escuro

---

## 🧪 Exemplo de uso

O código deve incluir:

* leitura de um JSON de exemplo
* chamada do render
* geração de páginas

---

## 🧠 Contexto

Esse sistema será usado em um app de geração de histórias com IA (MakeStory AI), então deve ser:

* modular
* escalável
* fácil de integrar com API

---

Gere código limpo, bem estruturado e pronto para produção.
