# Workflow: Ticket [Retenção]: Envio de E-mails Anti-Churn por UF

## Informações Gerais

| Campo | Valor |
|-------|-------|
| **Nome sugerido** | Ticket [Retenção]: Envio de e-mails anti-churn por UF |
| **Tipo** | TICKET_FLOW (Workflow de Ticket) |
| **Object Type ID** | 0-5 (Tickets) |
| **Re-enrollment** | Habilitado |

---

## Objetivo

Quando um ticket é **criado** no pipeline **"Retenção"**, o workflow:

1. Consulta a **tabela HubDB** pela `UF` do ticket → dados de segurança do estado
2. Busca o **e-mail do síndico (decisor)** via Airtable: Local → `endereco` → tabela `local` → e-mail representante legal
3. Envia **Modelo de E-mail A (síndico)** imediatamente ao criar o ticket
4. Aguarda o ticket entrar em **"Em tratativa"**
5. Envia **Modelo de E-mail B (moradores)** aos contatos associados ao local

O modelo de e-mail é selecionado dinamicamente pela UF do ticket.

> **Versão derivada de:** `workflow_churn_email_retenção.md`

---

## Fluxo Visual

```
[TRIGGER] Ticket criado no pipeline "Retenção"
    │
    ▼
[AÇÃO 1] Custom Code: Busca HubDB + Airtable + Dados do Local + Owner
    - Lê UF, owner_id do ticket
    - Consulta HubDB pela UF → protegidos, indiciados, ocorrencias
    - Busca Local → lê "endereco" (Identificador) e "logradouro"
    - Busca no Airtable pelo endereco → e-mail do síndico
    - Busca no HubSpot o contato com esse e-mail → exclui dos moradores
    - Resolve owner_id → nome, telefone, e-mail do responsável
    - Monta link WhatsApp
    - Seleciona IDs dos templates (síndico + moradores) pela UF
    │
    ▼
[BRANCH] UF encontrada na HubDB?
    │
    ├── SIM ──▶ [AÇÃO 2] Envia e-mail ao síndico (template por UF)
    │                │
    │                ▼
    │           [AGUARDAR ATÉ] hs_pipeline_stage = "Em tratativa" (timeout: 90 dias)
    │                │
    │                ▼
    │           [AÇÃO 3] Envia e-mail aos moradores (template por UF)
    │                │   + calcula previa (D+15 da data de envio)
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
| **Condição** | Ticket criado no pipeline "Retenção" |
| **Re-enrollment** | Sim |

---

## Ação 1 — Custom Code: Busca e Prepara Todos os Dados

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `automacao_hubspot`, `airtable_token` |
| **Input** | `ticket_id` ← `hs_object_id`, `uf_ocorrencia` ← `UF`, `owner_id` ← `hubspot_owner_id` |
| **Output** | `encontrado`, `protegidos`, `indiciados`, `ocorrencias`, `decisor_email`, `outros_contatos_json`, `proprietario_nome`, `wpp_ticket`, `email_ticket`, `endereco_logradouro`, `link_botao`, `template_sindico_id`, `template_moradores_id` |

### Código Python

```python
import os
import json
import requests
import unicodedata
import re
from typing import Optional, List, Set

HUBSPOT_TOKEN = os.environ["Hub_DB"]
AIRTABLE_TOKEN = os.environ["airtable_token"]
HUBDB_TABLE_ID = "224702045"
AIRTABLE_BASE_ID = "app1uxxj9gL9otgrB"
AIRTABLE_TABLE = "local"
AIRTABLE_FIELD_EMAIL = "fldpy0Ufbxm9K4iKq"  # e-mail representante legal

LOCAL_OBJECT_TYPE = "2-17828781"

HS_HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

# ─── Mapeamento de proprietários ──────────────────────────────────────────────
# Chave: hubspot_owner_id (string) | Valores: nome, telefone, e-mail

OWNERS = {
    "82534080": {
        "nome": "Juliana Oliveira",
        "telefone": "1193503-4998",
        "email": "juliana.oliveira@gabriel.com.br",
    },
    "87323353": {
        "nome": "Rô Almeida",
        "telefone": "1193503-5642",
        "email": "romilda.almeida@gabriel.com.br",
    },
    "76351551": {
        "nome": "Jonas Santos",
        "telefone": "1193503-4996",
        "email": "jonas.dangelo@gabriel.com.br",
    },
}

OWNER_FALLBACK = {
    "nome": "Isabella Beça",
    "telefone": "1193503-4875",
    "email": "isabella.beca@gabriel.com.br",
}

# ─── Templates de e-mail por UF ───────────────────────────────────────────────

TEMPLATES_SINDICO = {
    "sp": 208177673089,
    "rj": 208641991319,
    "mg": 208645552217,
}

TEMPLATES_MORADORES = {
    "sp": 208184624278,
    "rj": 208649333269,
    "mg": 208649371483,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.strip().lower())


def get_safe(url, headers, params=None):
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


# ─── HubDB ────────────────────────────────────────────────────────────────────

def buscar_uf_hubdb(nome_uf: str) -> Optional[dict]:
    url = f"https://api.hubapi.com/cms/v3/hubdb/tables/{HUBDB_TABLE_ID}/rows"
    uf_norm = normalizar(nome_uf)
    after = None

    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after

        data = get_safe(url, HS_HEADERS, params=params)
        resultados = data.get("results", [])

        for row in resultados:
            uf_row = normalizar(row.get("values", {}).get("uf", "") or "")
            if uf_row == uf_norm:
                return row

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

    return None


# ─── Airtable ─────────────────────────────────────────────────────────────────

def buscar_email_decisor_airtable(endereco: str) -> str:
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    params = {
        "filterByFormula": f'{{Título}}="{endereco}"',
        "fields[]": AIRTABLE_FIELD_EMAIL,
        "returnFieldsByFieldId": "true",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if records:
            return records[0].get("fields", {}).get(AIRTABLE_FIELD_EMAIL, "") or ""
    except Exception:
        pass
    return ""


# ─── Associações HubSpot ──────────────────────────────────────────────────────

def get_associacoes(objeto_tipo: str, objeto_id: str, tipo_associado: str) -> List[str]:
    url = f"https://api.hubapi.com/crm/v4/objects/{objeto_tipo}/{objeto_id}/associations/{tipo_associado}"
    dados = get_safe(url, HS_HEADERS)
    return [str(item["toObjectId"]) for item in dados.get("results", [])]


def get_propriedades_local(local_id: str, propriedades: List[str]) -> dict:
    url = f"https://api.hubapi.com/crm/v3/objects/{LOCAL_OBJECT_TYPE}/{local_id}"
    dados = get_safe(url, HS_HEADERS, params={"properties": ",".join(propriedades)})
    return dados.get("properties", {})


def buscar_contato_por_email(email: str) -> str:
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
        "properties": ["email"],
        "limit": 1,
    }
    try:
        resp = requests.post(url, headers=HS_HEADERS, json=payload, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return str(results[0]["id"])
    except Exception:
        pass
    return ""


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(event):
    inputs = event.get("inputFields", {})
    ticket_id = str(inputs.get("ticket_id", "")).strip()
    uf = str(inputs.get("uf_ocorrencia", "")).strip()
    owner_id = str(inputs.get("owner_id", "")).strip()

    # ── Resolve proprietário do ticket ────────────────────────────────────────
    owner = OWNERS.get(owner_id, OWNER_FALLBACK)
    proprietario_nome = owner["nome"]
    wpp_ticket = owner["telefone"]
    email_ticket = owner["email"]

    # ── Monta link WhatsApp ───────────────────────────────────────────────────
    wpp_digits = wpp_ticket.replace("-", "")
    link_botao = f"https://wa.me/55{wpp_digits}?text=Falar%20com%20o%20especialista"

    # ── Locais associados ao ticket ────────────────────────────────────────────
    locais_ids = get_associacoes("tickets", ticket_id, LOCAL_OBJECT_TYPE) if ticket_id else []

    # ── Decisor via Airtable + Logradouro do Local ─────────────────────────────
    decisor_email = ""
    decisor_contact_id = ""
    endereco_logradouro = ""
    if locais_ids:
        props_local = get_propriedades_local(locais_ids[0], ["endereco", "endereco_", "no_do_endereco"])
        identificador = props_local.get("endereco", "") or ""
        rua = props_local.get("endereco_", "") or ""
        numero = props_local.get("no_do_endereco", "") or ""
        endereco_logradouro = f"{rua} {numero}".strip()
        if identificador:
            decisor_email = buscar_email_decisor_airtable(identificador)

    # Busca o contato HubSpot do decisor para excluí-lo da lista de moradores
    if decisor_email:
        decisor_contact_id = buscar_contato_por_email(decisor_email)

    # ── Contatos dos locais (moradores) — exclui o decisor ────────────────────
    todos_contatos_local: Set[str] = set()
    for local_id in locais_ids:
        todos_contatos_local.update(get_associacoes(LOCAL_OBJECT_TYPE, local_id, "contacts"))

    outros_contatos_ids = [c for c in todos_contatos_local if c != decisor_contact_id]

    # ── Busca HubDB pela UF + seleciona templates ─────────────────────────────
    protegidos = ""
    indiciados = ""
    ocorrencias = ""
    encontrado = "0"
    uf_key = uf.strip().lower()
    template_sindico_id = str(TEMPLATES_SINDICO.get(uf_key, 0))
    template_moradores_id = str(TEMPLATES_MORADORES.get(uf_key, 0))

    if uf:
        row = buscar_uf_hubdb(uf)
        if row:
            values = row.get("values", {})
            protegidos = str(values.get("protegidos", "") or "")
            indiciados = str(values.get("indiciados", "") or "")
            ocorrencias = str(values.get("ocorrencias", "") or "")
            encontrado = "1"

    return {
        "outputFields": {
            "encontrado": encontrado,
            "uf_recebida": uf,
            "decisor_email": decisor_email,
            "outros_contatos_json": json.dumps(outros_contatos_ids),
            "protegidos": protegidos,
            "indiciados": indiciados,
            "ocorrencias": ocorrencias,
            "proprietario_nome": proprietario_nome,
            "wpp_ticket": wpp_ticket,
            "email_ticket": email_ticket,
            "endereco_logradouro": endereco_logradouro,
            "link_botao": link_botao,
            "template_sindico_id": template_sindico_id,
            "template_moradores_id": template_moradores_id,
        }
    }
```

---

## Branch — UF Encontrada?

| Condição | Destino |
|----------|---------|
| Output `encontrado` = `"1"` | Ramo SIM → Ação 2 |
| Caso contrário | Ramo NÃO → Fim |

---

## Ação 2 — Custom Code: Envia E-mail ao Síndico (Decisor)

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `automacao_hubspot` |
| **Input** | `decisor_email`, `protegidos`, `indiciados`, `ocorrencias`, `proprietario_nome`, `wpp_ticket`, `email_ticket`, `endereco_logradouro`, `link_botao`, `template_sindico_id` |
| **Output** | `enviado_sindico`, `erro_sindico` |

### Código Python

```python
import os
import json
import requests

HUBSPOT_TOKEN = os.environ["automacao_hubspot"]

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}


def enviar_email(email_address: str, template_id: int, custom_props: dict) -> tuple:
    url = "https://api.hubapi.com/marketing/v3/transactional/single-email/send"
    payload = {
        "emailId": template_id,
        "message": {"to": email_address},
        "customProperties": custom_props,
    }
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    return resp.status_code in (200, 201), f"{resp.status_code}:{resp.text[:300]}"


def main(event):
    inputs = event.get("inputFields", {})
    decisor_email = str(inputs.get("decisor_email", "")).strip()
    template_id = int(inputs.get("template_sindico_id", 0) or 0)

    custom_props = {
        "protegidos":          inputs.get("protegidos", ""),
        "indiciados":          inputs.get("indiciados", ""),
        "ocorrencias":         inputs.get("ocorrencias", ""),
        "proprietarioticket":  inputs.get("proprietario_nome", ""),
        "wppticket":           inputs.get("wpp_ticket", ""),
        "emailticket":         inputs.get("email_ticket", ""),
        "endereco":            inputs.get("endereco_logradouro", ""),
        "link_botao":          inputs.get("link_botao", ""),
    }

    enviado = "0"
    erro = ""

    if decisor_email and template_id:
        ok, motivo = enviar_email(decisor_email, template_id, custom_props)
        if ok:
            enviado = "1"
        else:
            erro = motivo

    return {
        "outputFields": {
            "enviado_sindico": enviado,
            "erro_sindico": erro,
        }
    }
```

---

## Aguardar Até — Ticket em "Em Tratativa"

| Campo | Valor |
|-------|-------|
| **Tipo** | Aguardar até propriedade |
| **Condição** | `hs_pipeline_stage` = ID do estágio "Em tratativa" |
| **Timeout** | 90 dias (ajustar conforme necessidade) |
| **Comportamento no timeout** | Encerrar o fluxo |

---

## Ação 3 — Custom Code: Envia E-mail aos Moradores

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `automacao_hubspot` |
| **Input** | `outros_contatos_json`, `protegidos`, `indiciados`, `ocorrencias`, `proprietario_nome`, `wpp_ticket`, `email_ticket`, `endereco_logradouro`, `link_botao`, `template_moradores_id` |
| **Output** | `emails_enviados`, `erros` |

### Código Python

```python
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List

HUBSPOT_TOKEN = os.environ["automacao_hubspot"]

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}


def get_email_contato(contact_id: str) -> Optional[str]:
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    resp = requests.get(url, headers=HEADERS, params={"properties": "email"}, timeout=30)
    if resp.status_code != 200:
        return None
    return resp.json().get("properties", {}).get("email")


def enviar_email(email_address: str, template_id: int, custom_props: dict) -> tuple:
    url = "https://api.hubapi.com/marketing/v3/transactional/single-email/send"
    payload = {
        "emailId": template_id,
        "message": {"to": email_address},
        "customProperties": custom_props,
    }
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    return resp.status_code in (200, 201), f"{resp.status_code}:{resp.text[:300]}"


def main(event):
    inputs = event.get("inputFields", {})
    outros_json = inputs.get("outros_contatos_json", "[]")
    template_id = int(inputs.get("template_moradores_id", 0) or 0)

    # D+15 a partir da data de envio deste e-mail
    previa = (datetime.utcnow() + timedelta(days=15)).strftime("%d/%m/%Y")

    custom_props = {
        "protegidos":          inputs.get("protegidos", ""),
        "indiciados":          inputs.get("indiciados", ""),
        "ocorrencias":         inputs.get("ocorrencias", ""),
        "proprietarioticket":  inputs.get("proprietario_nome", ""),
        "wppticket":           inputs.get("wpp_ticket", ""),
        "emailticket":         inputs.get("email_ticket", ""),
        "endereco":            inputs.get("endereco_logradouro", ""),
        "link_botao":          inputs.get("link_botao", ""),
        "previa":              previa,
    }

    try:
        parsed = json.loads(outros_json)
        outros_ids: List[str] = parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        outros_ids = []

    enviados = 0
    erros = []

    for cid in outros_ids:
        email = get_email_contato(cid)
        if not email:
            continue
        ok, motivo = enviar_email(email, template_id, custom_props)
        if ok:
            enviados += 1
        else:
            erros.append(f"{cid}|{motivo}")

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
| `encontrado` | String (`"0"` / `"1"`) | Se a UF foi localizada na HubDB |
| `uf_recebida` | String | Valor da UF recebida do ticket |
| `protegidos` | String | Protegidos no estado |
| `indiciados` | String | Indiciados no estado |
| `ocorrencias` | String | Ocorrências no estado |
| `decisor_email` | String | E-mail do síndico (Airtable) |
| `outros_contatos_json` | String (JSON array) | IDs dos contatos HubSpot associados ao local |
| `proprietario_nome` | String | Nome do responsável pelo ticket |
| `wpp_ticket` | String | Telefone do responsável (ex: `1193503-4998`) |
| `email_ticket` | String | E-mail do responsável |
| `endereco_logradouro` | String | Logradouro do local associado |
| `link_botao` | String | Link WhatsApp do responsável |
| `template_sindico_id` | String | ID do template do síndico para a UF |
| `template_moradores_id` | String | ID do template de moradores para a UF |

### Ação 2

| Output | Tipo | Descrição |
|--------|------|-----------|
| `enviado_sindico` | String (`"0"` / `"1"`) | Se o e-mail ao síndico foi enviado |
| `erro_sindico` | String | Detalhe do erro, se houver |

### Ação 3

| Output | Tipo | Descrição |
|--------|------|-----------|
| `emails_enviados` | String (número) | Total de e-mails enviados com sucesso |
| `erros` | String (JSON array) | IDs de contatos com falha no envio |

---

## Templates de E-mail por UF

### Síndico (Decisor)

| UF | Template ID |
|----|------------|
| SP | 208177673089 |
| RJ | 208641991319 |
| MG | 208645552217 |

### Moradores

| UF | Template ID |
|----|------------|
| SP | 208184624278 |
| RJ | 208649333269 |
| MG | 208649371483 |

---

## Mapeamento de Proprietários

| Owner ID HubSpot | Nome | Telefone | E-mail |
|-----------------|------|----------|--------|
| 82534080 | Juliana Oliveira | 1193503-4998 | juliana.oliveira@gabriel.com.br |
| 87323353 | Rô Almeida | 1193503-5642 | romilda.almeida@gabriel.com.br |
| 76351551 | Jonas Santos | 1193503-4996 | jonas.dangelo@gabriel.com.br |
| _(fallback)_ | Isabella Beça | 1193503-4875 | isabella.beca@gabriel.com.br |

---

## Configurações a Confirmar no HubSpot

| O que confirmar | Variável no código |
|-----------------|-------------------|
| Nome interno da propriedade `UF` no ticket | `uf_ocorrencia` no input |
| Nome interno da propriedade `Logradouro` no Local | `logradouro` — confirmar em Config > Propriedades > Objetos personalizados > Local |
| ID do estágio "Em tratativa" | Na ação "Aguardar até" |
| Secret `airtable_token` criado no HubSpot | Config > Integrações > Código privado > Segredos |

---

## Configuração no HubSpot (passo a passo)

### 1. Criar o Workflow
- Automação > Workflows > Criar workflow
- Tipo: **Baseado em ticket**
- Trigger: ticket criado no pipeline "Retenção"
- Habilitar re-enrollment

### 2. Adicionar Ação 1 — Custom Code
- **Inputs:** `ticket_id` (hs_object_id), `uf_ocorrencia` (UF), `owner_id` (hubspot_owner_id)
- **Outputs:** todos os 14 campos listados acima
- **Secrets:** `automacao_hubspot`, `airtable_token`

### 3. Adicionar Branch
- `encontrado` = `"1"` → ramo SIM

### 4. Adicionar Ação 2 — Custom Code (síndico)
- **Inputs:** `decisor_email`, `protegidos`, `indiciados`, `ocorrencias`, `proprietario_nome`, `wpp_ticket`, `email_ticket`, `endereco_logradouro`, `link_botao`, `template_sindico_id`
- **Secret:** `automacao_hubspot`

### 5. Adicionar "Aguardar até"
- Propriedade `hs_pipeline_stage` = ID de "Em tratativa"
- Timeout: 90 dias → encerrar

### 6. Adicionar Ação 3 — Custom Code (moradores)
- **Inputs:** `outros_contatos_json`, `protegidos`, `indiciados`, `ocorrencias`, `proprietario_nome`, `wpp_ticket`, `email_ticket`, `endereco_logradouro`, `link_botao`, `template_moradores_id`
- **Secret:** `automacao_hubspot`

---

## Diagrama de Relacionamento

```
TICKET (pipeline: Retenção)
  │  propriedades: UF, hubspot_owner_id
  │
  └── [associação] ──▶ LOCAL (objeto customizado)
                           │  propriedades: endereco (Identificador), logradouro
                           │
                           ├── [Airtable: Título = endereco]
                           │       └── e-mail representante legal → Modelo A (síndico)
                           │
                           └── [contatos associados ao local] → Modelo B (moradores)
```

---

## Observações

- O nome interno da propriedade `Logradouro` no Local precisa ser confirmado em Config > Propriedades > Objetos personalizados > Local (usado como `logradouro` no código)
- Se o owner do ticket estiver vazio ou não constar no mapeamento, o fallback é Isabella Beça automaticamente
- `previa` é calculado no momento do envio dos moradores (D+15 da data em que o ticket entrou em "Em tratativa"), não na criação do ticket
- Se o ticket nunca chegar em "Em tratativa" dentro de 90 dias, o e-mail dos moradores não é enviado
- Os secrets `automacao_hubspot` e `airtable_token` devem ser declarados explicitamente em cada ação que os utiliza
