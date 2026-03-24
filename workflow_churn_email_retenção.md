# Workflow: Ticket [Retenção]: Envio de E-mails Anti-Churn

## Informações Gerais

| Campo | Valor |
|-------|-------|
| **Nome sugerido** | Ticket [Retenção]: Envio de e-mails anti-churn por bairro |
| **Tipo** | TICKET_FLOW (Workflow de Ticket) |
| **Object Type ID** | 0-5 (Tickets) |
| **Re-enrollment** | Habilitado |

---

## Objetivo

Quando um ticket entra no estágio **"Em tratativa"** do pipeline **"Retenção"**, o workflow:

1. Consulta a **tabela HubDB** usando o campo `bairro_ocorrencia` do ticket para buscar dados de segurança do bairro
2. Identifica o **contato decisor** (associado diretamente ao ticket) → recebe **Modelo de E-mail A**
3. Navega pela hierarquia: **Ticket → Locais (Empresas) → Negócios (pipeline "executivo de vendas 2.0") → Contatos** → esses contatos não-decisores recebem **Modelo de E-mail B**

---

## Fluxo Visual

```
[TRIGGER] Ticket entra em "Em tratativa" no pipeline "Retenção"
    │
    ▼
[AÇÃO 1] Custom Code: Busca HubDB + Monta lista de contatos
    - Lê bairro_ocorrencia do ticket
    - Consulta HubDB pelo bairro → protegidos, indiciados, ocorrencias
    - Busca contato associado ao ticket (decisor)
    - Busca locais (empresas) associados ao ticket
    - Para cada local → busca negócios no pipeline "executivo de vendas 2.0"
    - Para cada negócio → busca todos os contatos associados
    - Separa: decisor vs. demais contatos
    │
    ▼
[BRANCH] Bairro encontrado na HubDB?
    │
    ├── SIM ──▶ [AÇÃO 2] Custom Code: Envia Modelo A ao decisor
    │                │       + Envia Modelo B aos demais contatos
    │                ▼
    │           [FIM]
    │
    └── NÃO ──▶ [FIM]
```

---

## Trigger

| Campo | Valor |
|-------|-------|
| **Tipo** | Baseado em propriedade do ticket |
| **Pipeline** | Retenção (confirmar ID interno) |
| **Estágio** | Em tratativa (confirmar ID interno do estágio) |
| **Condição** | `hs_pipeline_stage` = ID do estágio "Em tratativa" |
| **Re-enrollment** | Sim — re-executa se o ticket retornar a esse estágio |

> **Como obter os IDs:** HubSpot > Configurações > Objetos > Tickets > Pipelines > clique no pipeline "Retenção" e inspecione a URL ou use a API `GET /crm/v3/pipelines/tickets`.

---

## Ação 1 — Custom Code: Busca HubDB + Monta Lista de Contatos

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `automacao_hubspot` |
| **Input** | `ticket_id` ← `hs_object_id` do ticket, `bairro_ocorrencia` ← propriedade do ticket |
| **Output** | `encontrado`, `protegidos`, `indiciados`, `ocorrencias`, `decisor_contact_id`, `outros_contatos_json` |

### Código Python

```python
import os
import json
import requests
import unicodedata
import re
from typing import Optional, List, Set

HUBSPOT_TOKEN = os.environ["Hub_DB"]
HUBDB_TABLE_ID = "224700702"

# Tipo do objeto customizado "Local" no HubSpot (formato: "2-XXXXXXX")
# Para descobrir: Configurações > Objetos > Objetos personalizados > Local > copiar o ID da URL
LOCAL_OBJECT_TYPE = "2-17828781"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.strip().lower())


def get_safe(url, params=None):
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


# ─── HubDB ────────────────────────────────────────────────────────────────────

def buscar_bairro_hubdb(nome_bairro: str) -> Optional[dict]:
    url = f"https://api.hubapi.com/cms/v3/hubdb/tables/{HUBDB_TABLE_ID}/rows"
    bairro_norm = normalizar(nome_bairro)
    after = None

    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after

        data = get_safe(url, params=params)
        resultados = data.get("results", [])

        for row in resultados:
            # Tenta nome na coluna "name" dentro de values (coluna customizada)
            nome_values = row.get("values", {}).get("name", "") or ""
            # Tenta também o campo "name" de nível raiz (nome padrão da row)
            nome_root = row.get("name", "") or ""
            if normalizar(nome_values) == bairro_norm or normalizar(nome_root) == bairro_norm:
                return row

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

    return None


# ─── Associações HubSpot ──────────────────────────────────────────────────────

def get_associacoes(objeto_tipo: str, objeto_id: str, tipo_associado: str) -> List[str]:
    url = f"https://api.hubapi.com/crm/v4/objects/{objeto_tipo}/{objeto_id}/associations/{tipo_associado}"
    dados = get_safe(url)
    return [str(item["toObjectId"]) for item in dados.get("results", [])]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(event):
    inputs = event.get("inputFields", {})
    ticket_id = str(inputs.get("ticket_id", "")).strip()
    bairro = str(inputs.get("bairro_ocorrencia", "")).strip()

    # ── Busca contatos SEMPRE (independente do HubDB) ──────────────────────────

    # 1. Contato decisor (associado direto ao ticket)
    contatos_ticket = get_associacoes("tickets", ticket_id, "contacts") if ticket_id else []
    decisor_id = contatos_ticket[0] if contatos_ticket else ""

    # 2. Locais associados ao ticket (objeto customizado)
    locais_ids = get_associacoes("tickets", ticket_id, LOCAL_OBJECT_TYPE) if ticket_id else []

    # 3. Para cada local → contatos diretos
    todos_contatos_local: Set[str] = set()
    for local_id in locais_ids:
        todos_contatos_local.update(get_associacoes(LOCAL_OBJECT_TYPE, local_id, "contacts"))

    outros_contatos = [c for c in todos_contatos_local if c != decisor_id]

    # ── Busca HubDB pelo bairro ────────────────────────────────────────────────
    protegidos = ""
    indiciados = ""
    ocorrencias = ""
    encontrado = "0"

    if bairro:
        row = buscar_bairro_hubdb(bairro)
        if row:
            values = row.get("values", {})
            protegidos = str(values.get("protegidos", "") or "")
            indiciados = str(values.get("indiciados", "") or "")
            ocorrencias = str(values.get("ocorrencias", "") or "")
            encontrado = "1"

    return {
        "outputFields": {
            "encontrado": encontrado,
            "bairro_recebido": bairro,              # debug: confirma o valor recebido
            "decisor_contact_id": decisor_id,
            "outros_contatos_json": json.dumps(outros_contatos),
            "locais_ids_json": json.dumps(locais_ids),   # debug: confirma os locais
            "protegidos": protegidos,
            "indiciados": indiciados,
            "ocorrencias": ocorrencias,
        }
    }
```

---

## Branch — Bairro Encontrado?

| Condição | Destino |
|----------|---------|
| Output `encontrado` = `"1"` | Ramo SIM → Ação 2 |
| Caso contrário | Ramo NÃO → Fim |

---

## Ação 2 — Custom Code: Envia E-mails (Modelo A e Modelo B)

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `automacao_hubspot` |
| **Input** | `decisor_contact_id`, `outros_contatos_json`, `protegidos`, `indiciados`, `ocorrencias` |
| **Output** | `emails_enviados` (número total), `erros` (lista de IDs com falha) |

### Código Python

```python
import os
import json
import requests
from typing import Optional, List

HUBSPOT_TOKEN = os.environ["automacao_hubspot"]

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

# IDs dos templates de e-mail transacional no HubSpot — confirmar nos templates
EMAIL_MODELO_A_ID = SEU_EMAIL_A_ID_AQUI   # Modelo para o decisor
EMAIL_MODELO_B_ID = SEU_EMAIL_B_ID_AQUI   # Modelo para demais contatos


def get_email_contato(contact_id: str) -> Optional[str]:
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    resp = requests.get(url, headers=HEADERS, params={"properties": "email"}, timeout=30)
    if resp.status_code != 200:
        return None
    return resp.json().get("properties", {}).get("email")


def enviar_email(contact_id: str, email_address: str, template_id: int, props: dict) -> bool:
    url = "https://api.hubapi.com/marketing/v3/transactional/single-email/send"
    payload = {
        "emailId": template_id,
        "message": {"to": email_address},
        "contactProperties": {
            "protegidos_bairro": props["protegidos"],
            "indiciados_bairro": props["indiciados"],
            "ocorrencias_bairro": props["ocorrencias"],
        },
        "customProperties": {
            "protegidos": props["protegidos"],
            "indiciados": props["indiciados"],
            "ocorrencias": props["ocorrencias"],
        },
    }
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    return resp.status_code in (200, 201)


def main(event):
    inputs = event.get("inputFields", {})
    decisor_id = str(inputs.get("decisor_contact_id", "")).strip()
    outros_json = inputs.get("outros_contatos_json", "[]")
    props = {
        "protegidos": inputs.get("protegidos", ""),
        "indiciados": inputs.get("indiciados", ""),
        "ocorrencias": inputs.get("ocorrencias", ""),
    }

    try:
        outros_ids: List[str] = json.loads(outros_json)
    except (json.JSONDecodeError, TypeError):
        outros_ids = []

    enviados = 0
    erros = []

    # Envia Modelo A ao decisor
    if decisor_id:
        email_decisor = get_email_contato(decisor_id)
        if email_decisor:
            ok = enviar_email(decisor_id, email_decisor, EMAIL_MODELO_A_ID, props)
            if ok:
                enviados += 1
            else:
                erros.append(f"decisor:{decisor_id}")

    # Envia Modelo B aos demais contatos
    for cid in outros_ids:
        email = get_email_contato(cid)
        if not email:
            continue
        ok = enviar_email(cid, email, EMAIL_MODELO_B_ID, props)
        if ok:
            enviados += 1
        else:
            erros.append(f"outros:{cid}")

    return {
        "outputFields": {
            "emails_enviados": str(enviados),
            "erros": json.dumps(erros),
        }
    }
```

---

## Outputs das Custom Codes

### Ação 1

| Output | Tipo | Descrição |
|--------|------|-----------|
| `encontrado` | String (`"0"` / `"1"`) | Se o bairro foi localizado na HubDB |
| `protegidos` | String (número) | Protegidos no bairro |
| `indiciados` | String (número) | Indiciados no bairro |
| `ocorrencias` | String (número) | Ocorrências no bairro |
| `decisor_contact_id` | String | ID do contato decisor (associado direto ao ticket) |
| `outros_contatos_json` | String (JSON array) | IDs dos demais contatos vinculados via local → negócio |

### Ação 2

| Output | Tipo | Descrição |
|--------|------|-----------|
| `emails_enviados` | String (número) | Total de e-mails enviados com sucesso |
| `erros` | String (JSON array) | IDs de contatos com falha no envio |

---

## Configurações a Confirmar no HubSpot

Antes de ativar o workflow, você precisa levantar os seguintes IDs:

| O que confirmar | Como encontrar | Variável no código |
|-----------------|---------------|-------------------|
| **ID da tabela HubDB** de bairros | Marketing > HubDB > abrir tabela > URL do navegador | `HUBDB_TABLE_ID` |
| **ID do pipeline** "Retenção" (tickets) | Config > Objetos > Tickets > Pipelines | No trigger do workflow |
| **ID do estágio** "Em tratativa" | Mesmo lugar acima | No trigger do workflow |
| **ID do pipeline** "Executivo de Vendas 2.0" (deals) | `79388826` (confirmado) | `PIPELINE_EXECUTIVO_ID` |
| **ID do template** de e-mail Modelo A (decisor) | Marketing > E-mail > Templates | `EMAIL_MODELO_A_ID` |
| **ID do template** de e-mail Modelo B (demais) | Marketing > E-mail > Templates | `EMAIL_MODELO_B_ID` |
| **Nome interno** da propriedade "Bairro (Ocorrência)" no ticket | Config > Propriedades > Filtrar por Tickets | `bairro_ocorrencia` no input |

---

## Nomes das Colunas no HubDB

O código usa os seguintes nomes de coluna — confirmar que batem com a tabela:

| Variável no código | Coluna no HubDB |
|--------------------|----------------|
| `values["name"]` | `name` (nome do bairro) |
| `values["protegidos"]` | `protegidos` |
| `values["indiciados"]` | `indiciados` |
| `values["ocorrencias"]` | `ocorrencias` |

---

## Configuração no HubSpot (passo a passo)

### 1. Criar o Workflow
- Automação > Workflows > Criar workflow
- Tipo: **Baseado em ticket**
- Trigger: propriedade `hs_pipeline_stage` = ID de "Em tratativa" no pipeline "Retenção"
- Habilitar re-enrollment

### 2. Adicionar Ação 1 — Custom Code
- Tipo: Código personalizado | Runtime: Python 3.9
- **Inputs:**
  - `ticket_id` → propriedade do ticket `hs_object_id`
  - `bairro_ocorrencia` → propriedade do ticket "Bairro (Ocorrência)"
- **Outputs:** declarar `encontrado`, `protegidos`, `indiciados`, `ocorrencias`, `decisor_contact_id`, `outros_contatos_json`
- **Secret:** `automacao_hubspot`

### 3. Adicionar Branch
- Output `encontrado` (da Ação 1) = `"1"` → ramo SIM
- Caso contrário → fim

### 4. Adicionar Ação 2 — Custom Code (no ramo SIM)
- Tipo: Código personalizado | Runtime: Python 3.9
- **Inputs:**
  - `decisor_contact_id` ← output da Ação 1
  - `outros_contatos_json` ← output da Ação 1
  - `protegidos` ← output da Ação 1
  - `indiciados` ← output da Ação 1
  - `ocorrencias` ← output da Ação 1
- **Outputs:** declarar `emails_enviados`, `erros`
- **Secret:** `automacao_hubspot`

---

## Diagrama de Relacionamento

```
TICKET (pipeline: Retenção, estágio: Em tratativa)
  │
  ├── [associação direta] ──▶ CONTATO (decisor) → E-mail Modelo A
  │
  └── [associação] ──▶ LOCAL (Empresa/Company)
                           │
                           └── [associação] ──▶ NEGÓCIO (Deal)
                                                    │ filtrado por pipeline
                                                    │ "executivo de vendas 2.0"
                                                    │
                                                    └── [associação] ──▶ CONTATOS
                                                                          (exceto decisor)
                                                                          → E-mail Modelo B
```

---

## Observações

- O campo `bairro_ocorrencia` no código deve bater com o nome interno da propriedade do ticket — confirmar em Config > Propriedades > Tickets
- Se o ticket não tiver contato associado, `decisor_id` ficará vazio e o Modelo A não será enviado (sem erro)
- Se nenhum negócio do local estiver no pipeline "executivo de vendas 2.0", a lista de outros contatos ficará vazia — apenas o decisor recebe e-mail
- Os e-mails são enviados via **Transactional Email API** do HubSpot, que requer que os templates estejam configurados como "transacional" e que o módulo de e-mail transacional esteja ativo no portal
- As propriedades `protegidos_bairro`, `indiciados_bairro`, `ocorrencias_bairro` podem ser usadas como tokens de personalização nos templates de e-mail
