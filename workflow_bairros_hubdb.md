# Workflow: Contato [Bairro]: Enriquece dados pelo HubDB

## Informações Gerais

| Campo | Valor |
|-------|-------|
| **Nome sugerido** | Contato [Bairro]: Enriquece dados de segurança pelo bairro |
| **Tipo** | CONTACT_FLOW (Workflow de Contato) |
| **Object Type ID** | 0-1 (Contatos) |
| **Re-enrollment** | Habilitado |

---

## Objetivo

Quando o bairro de um contato for preenchido ou alterado, o workflow consulta a tabela HubDB de bairros e atualiza as propriedades do contato com os dados de segurança correspondentes:

- **Protegidos no bairro** → `protegidos_bairro`
- **Indiciados no bairro** → `indiciados_bairro`
- **Ocorrências no bairro** → `ocorrencias_bairro`

---

## Trigger

| Campo | Valor |
|-------|-------|
| **Tipo** | Baseado em evento (EVENT_BASED) |
| **Propriedade** | `bairro` (bairro do contato) |
| **Condição** | Quando valor é conhecido (preenchido ou alterado) |
| **Re-enrollment** | Sim — re-executa quando bairro mudar |

---

## Estrutura de Ações

```
[TRIGGER] Propriedade "bairro" alterada
    │
    ▼
[BRANCH] Bairro está preenchido?
    │
    ├── SIM ──▶ [AÇÃO 1] Custom Code: Consulta HubDB pelo bairro
    │                │
    │                ▼
    │           [BRANCH] Bairro encontrado na tabela?
    │                │
    │                ├── SIM ──▶ [AÇÃO 2] Atualiza propriedades do contato
    │                │
    │                └── NÃO ──▶ [FIM] (bairro não cadastrado)
    │
    └── NÃO ──▶ [FIM]
```

---

## Ação 1 — Custom Code: Consulta HubDB

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `automacao_hubspot` |
| **Input** | `bairro` ← propriedade do contato |
| **Output** | `protegidos`, `indiciados`, `ocorrencias`, `encontrado` |

### Código Python

```python
import os
import requests
import unicodedata
import re

HUBSPOT_TOKEN = os.environ["automacao_hubspot"]

# ID da tabela HubDB de bairros — substitua pelo ID real
HUBDB_TABLE_ID = "SEU_TABLE_ID_AQUI"


def normalizar(texto: str) -> str:
    """Remove acentos e converte para minúsculas para comparação."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.strip().lower())


def buscar_bairro_hubdb(nome_bairro: str) -> dict | None:
    """
    Consulta a tabela HubDB filtrando pelo nome do bairro.
    Usa o parâmetro 'name__icontains' para busca case-insensitive.
    """
    url = f"https://api.hubapi.com/cms/v3/hubdb/tables/{HUBDB_TABLE_ID}/rows"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }
    params = {
        "name__icontains": nome_bairro,
        "limit": 5,
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    resultados = response.json().get("results", [])

    if not resultados:
        return None

    # Se retornou mais de 1, tenta match exato por normalização
    bairro_normalizado = normalizar(nome_bairro)
    for row in resultados:
        nome_na_tabela = row.get("values", {}).get("name", "")
        if normalizar(nome_na_tabela) == bairro_normalizado:
            return row

    # Se não achou match exato, retorna o primeiro resultado
    return resultados[0]


def main(event):
    bairro = event.get("inputFields", {}).get("bairro", "").strip()

    if not bairro:
        return {
            "outputFields": {
                "encontrado": "0",
                "protegidos": "",
                "indiciados": "",
                "ocorrencias": "",
            }
        }

    row = buscar_bairro_hubdb(bairro)

    if not row:
        return {
            "outputFields": {
                "encontrado": "0",
                "protegidos": "",
                "indiciados": "",
                "ocorrencias": "",
            }
        }

    values = row.get("values", {})

    return {
        "outputFields": {
            "encontrado": "1",
            "protegidos": str(values.get("protegidos", "") or ""),
            "indiciados": str(values.get("indiciados", "") or ""),
            "ocorrencias": str(values.get("ocorrencias", "") or ""),
        }
    }
```

---

## Ação 2 — Branch: Bairro encontrado?

| Condição | Valor |
|----------|-------|
| **Output** `encontrado` | igual a `"1"` → branch SIM |
| Caso contrário | branch NÃO → fim do fluxo |

---

## Ação 3 — Atualizar Propriedades do Contato

Atualiza as seguintes propriedades com os outputs da Ação 1:

| Propriedade HubSpot | Output da Custom Code | Tipo sugerido |
|---------------------|----------------------|---------------|
| `protegidos_bairro` | `protegidos` | Número |
| `indiciados_bairro` | `indiciados` | Número |
| `ocorrencias_bairro` | `ocorrencias` | Número |

---

## Propriedades a Criar no HubSpot

Antes de configurar o workflow, crie estas propriedades no HubSpot:

| Nome interno | Rótulo | Tipo | Grupo sugerido |
|-------------|--------|------|----------------|
| `protegidos_bairro` | Protegidos no Bairro | Número | Informações do Bairro |
| `indiciados_bairro` | Indiciados no Bairro | Número | Informações do Bairro |
| `ocorrencias_bairro` | Ocorrências no Bairro | Número | Informações do Bairro |
| `bairro` | Bairro | Texto de linha única | Informações de Endereço |

> **Obs.:** Se a propriedade `bairro` já existir, não precisa recriar.

---

## Como obter o Table ID da HubDB

1. No HubSpot, vá em **Marketing > Arquivos e Templates > HubDB**
2. Abra a tabela de bairros
3. Na URL do navegador, copie o número após `/hubdb/`:
   ```
   https://app.hubspot.com/hubdb/XXXXXXXX/tables/SEU_TABLE_ID_AQUI/edit
   ```
4. Substitua `SEU_TABLE_ID_AQUI` no código Python acima

---

## Nomes das Colunas no HubDB

O código usa os seguintes nomes de coluna — confirme que batem com a tabela:

| Variável no código | Nome da coluna no HubDB |
|--------------------|------------------------|
| `values["name"]` | `name` (nome do bairro — coluna padrão) |
| `values["protegidos"]` | `protegidos` |
| `values["indiciados"]` | `indiciados` |
| `values["ocorrencias"]` | `ocorrencias` |

> Para verificar os nomes internos das colunas: HubDB > sua tabela > **Manage Columns** > coluna "Column Name".

---

## Configuração no HubSpot (passo a passo)

### 1. Criar o Workflow
- Automação > Workflows > Criar workflow
- Tipo: **Baseado em contato**
- Trigger: Propriedade `bairro` é conhecida (com re-enrollment)

### 2. Adicionar Branch inicial
- "O contato tem bairro preenchido?" → `bairro` não está vazio

### 3. Adicionar Custom Code (Ação 1)
- Tipo: Código personalizado
- Runtime: Python 3.9
- Colar o código acima
- **Input:** mapear `bairro` → propriedade HubSpot `bairro`
- **Output:** declarar `encontrado`, `protegidos`, `indiciados`, `ocorrencias`
- **Secret:** `automacao_hubspot`

### 4. Adicionar Branch (Ação 2)
- Output `encontrado` = `"1"`

### 5. Adicionar "Definir valor de propriedade" (Ação 3)
- `protegidos_bairro` ← output `protegidos`
- `indiciados_bairro` ← output `indiciados`
- `ocorrencias_bairro` ← output `ocorrencias`

---

## Observações

- A busca por `name__icontains` é case-insensitive nativamente na API HubDB
- A normalização de acentos garante que "Aclimaçao" encontre "Aclimação"
- O workflow re-executa automaticamente se o bairro do contato for atualizado
- Se o bairro não existir na tabela HubDB, as propriedades não são alteradas (evita sobrescrever dados válidos com vazio)
