# Workflow: [Ticket] - E-mail Off Boarding (Dados em Tempo Real) V3

## Informações Gerais

| Campo | Valor |
|-------|-------|
| **ID** | `1796684196` |
| **Nome** | [Ticket] - E-mail Off Boarding (Dados em Tempo Real) V3 |
| **Tipo** | PLATFORM_FLOW (Workflow de Ticket) |
| **Object Type ID** | 0-5 (Tickets) |
| **Re-enrollment** | Desabilitado |
| **Revisão** | 25 |
| **Criado em** | 2026-03-26 |
| **Atualizado em** | 2026-03-30 |

---

## Objetivo

Quando um ticket é criado no pipeline **"Retenção"** (ID: `52153112`), com as condições:
- `tipo_de_retencao` **NÃO** é "Proativa"
- `motivo_do_cancelamento` **NÃO** é "Inadimplente"

O workflow:

1. Aguarda **10 minutos**
2. Consulta a **tabela HubDB** pela `UF` do ticket → dados de segurança do estado
3. Busca o **e-mail do síndico (decisor)** via Airtable: Local → `endereco` → tabela `local` → e-mail representante legal
4. Envia **Modelo de E-mail A (síndico)** — template selecionado pela UF
5. Aguarda o ticket entrar em **"Em tratativa"** (stage ID: `105781013`)
6. Envia **Modelo de E-mail B (moradores)** aos contatos associados ao local — com `previa` (D+15)

---

## Fluxo Visual

```
[TRIGGER] Ticket criado no pipeline "Retenção" (52153112)
    │      Filtros: tipo_de_retencao ≠ "Proativa"
    │               motivo_do_cancelamento ≠ "Inadimplente"
    │
    ▼
[DELAY] Aguardar 10 minutos (Action 6)
    │
    ▼
[AÇÃO 1] Custom Code: Busca HubDB + Airtable + Dados do Local + Owner (Action 1)
    - Lê UF, owner_id do ticket
    - Consulta HubDB pela UF → protegidos, indiciados, ocorrencias
    - Busca Local → lê "endereco" (Identificador), "endereco_" e "no_do_endereco"
    - Busca no Airtable pelo endereco → e-mail do síndico
    - Busca no HubSpot o contato com esse e-mail → exclui dos moradores
    - Resolve owner_id → nome, telefone, e-mail do responsável
    - Monta link WhatsApp
    - Seleciona IDs dos templates (síndico + moradores) pela UF
    │
    ▼
[BRANCH] encontrado = "1"? (Action 2)
    │
    ├── SIM ──▶ [AÇÃO 2] Envia e-mail ao síndico (Action 7)
    │                │
    │                ▼
    │           [AGUARDAR EVENTO] Ticket muda para stage "Em tratativa" (Action 8)
    │                │   Timeout: 86400 minutos (60 dias)
    │                │
    │                ▼
    │           [BRANCH] Critérios do evento atendidos? (Action 9)
    │                │
    │                ├── SIM ──▶ [AÇÃO 3] Envia e-mail aos moradores (Action 10)
    │                │                │   + calcula previa (D+15)
    │                │                ▼
    │                │           [FIM]
    │                │
    │                └── NÃO ──▶ [FIM] (Critérios de eventos não atendidos)
    │
    └── NÃO ──▶ [FIM]
```

---

## Trigger (Enrollment Criteria)

| Campo | Valor |
|-------|-------|
| **Tipo** | LIST_BASED |
| **Pipeline** | `52153112` (Retenção) |
| **Filtro 1** | `tipo_de_retencao` IS_NONE_OF "Proativa" |
| **Filtro 2** | `motivo_do_cancelamento` IS_NONE_OF "Inadimplente" |
| **Re-enrollment** | Desabilitado |
| **Un-enroll se critério não atendido** | Não |

---

## Action 6 — Delay (10 minutos)

| Campo | Valor |
|-------|-------|
| **Tipo** | SINGLE_CONNECTION (actionTypeId: 0-1) |
| **Delta** | 10 |
| **Unidade** | MINUTES |
| **Próxima ação** | Action 1 |

---

## Action 1 — Custom Code: Busca e Prepara Todos os Dados

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `Hub_DB`, `automacao_hubspot`, `airtable_token` |
| **Próxima ação** | Action 2 (branch) |

### Inputs

| Nome | Propriedade | Tipo |
|------|-------------|------|
| `ticket_id` | `hs_object_id` | OBJECT_PROPERTY |
| `uf_ocorrencia` | `estado__ocorrencia_` | OBJECT_PROPERTY |
| `owner_id` | `hubspot_owner_id` | OBJECT_PROPERTY |

### Outputs

| Nome | Tipo |
|------|------|
| `decisor_email` | STRING |
| `email_ticket` | STRING |
| `encontrado` | STRING |
| `endereco_logradouro` | STRING |
| `indiciados` | STRING |
| `link_botao` | STRING |
| `ocorrencias` | STRING |
| `outros_contatos_json` | STRING |
| `owner_id` | STRING |
| `proprietario_nome` | STRING |
| `protegidos` | STRING |
| `template_moradores_id` | STRING |
| `template_sindico_id` | STRING |
| `wpp_ticket` | STRING |

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
AIRTABLE_FIELD_EMAIL = "fldpy0Ufbxm9K4iKq"

LOCAL_OBJECT_TYPE = "2-17828781"

HS_HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

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
            valor = records[0].get("fields", {}).get(AIRTABLE_FIELD_EMAIL, "") or ""
            if isinstance(valor, list):
                return valor[0] if valor else ""
            if isinstance(valor, str) and valor.startswith("["):
                try:
                    parsed = json.loads(valor)
                    if isinstance(parsed, list):
                        return parsed[0] if parsed else ""
                except Exception:
                    pass
            return valor
    except Exception:
        pass
    return ""


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


def main(event):
    inputs = event.get("inputFields", {})
    ticket_id = str(inputs.get("ticket_id", "")).strip()
    uf = str(inputs.get("uf_ocorrencia", "")).strip()
    owner_id = str(inputs.get("owner_id", "")).strip()

    owner = OWNERS.get(owner_id, OWNER_FALLBACK)
    proprietario_nome = owner["nome"]
    wpp_ticket = owner["telefone"]
    email_ticket = owner["email"]

    wpp_digits = wpp_ticket.replace("-", "")
    link_botao = f"https://wa.me/55{wpp_digits}?text=Falar%20com%20o%20especialista"

    locais_ids = get_associacoes("tickets", ticket_id, LOCAL_OBJECT_TYPE) if ticket_id else []

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

    if decisor_email:
        decisor_contact_id = buscar_contato_por_email(decisor_email)

    todos_contatos_local: Set[str] = set()
    for local_id in locais_ids:
        todos_contatos_local.update(get_associacoes(LOCAL_OBJECT_TYPE, local_id, "contacts"))

    outros_contatos_ids = [c for c in todos_contatos_local if c != decisor_contact_id]

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
            "debug_owner_id": owner_id,
        }
    }
```

---

## Action 2 — Branch: UF Encontrada?

| Condição | Destino |
|----------|---------|
| `encontrado` (da Action 1) = `"1"` | Action 7 (envio síndico) |
| Caso contrário | Fim |

---

## Action 7 — Custom Code: Envia E-mail ao Síndico (Decisor)

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `Hub_DB` |
| **Próxima ação** | Action 8 (aguardar evento) |

### Inputs

| Nome | Origem |
|------|--------|
| `decisor_email` | Action 1 → `decisor_email` |
| `protegidos` | Action 1 → `protegidos` |
| `indiciados` | Action 1 → `indiciados` |
| `ocorrencias` | Action 1 → `ocorrencias` |
| `proprietario_nome` | Action 1 → `proprietario_nome` |
| `wpp_ticket` | Action 1 → `wpp_ticket` |
| `email_ticket` | Action 1 → `email_ticket` |
| `endereco_logradouro` | Action 1 → `endereco_logradouro` |
| `link_botao` | Action 1 → `link_botao` |
| `template_sindico_id` | Action 1 → `template_sindico_id` |

### Outputs

| Nome | Tipo |
|------|------|
| `enviado_sindico` | STRING |
| `erro_sindico` | STRING |
| `erros` | STRING |

### Código Python

```python
import os
import json
import requests

HUBSPOT_TOKEN = os.environ["Hub_DB"]

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

## Action 8 — Aguardar Evento: Ticket em "Em Tratativa"

| Campo | Valor |
|-------|-------|
| **Tipo** | SINGLE_CONNECTION (actionTypeId: 0-29) |
| **Evento** | `hs_pipeline_stage` muda para `105781013` ("Em tratativa") |
| **Event Type ID** | `4-655002` |
| **Timeout** | 86400 minutos (60 dias) |
| **Próxima ação** | Action 9 (branch) |

---

## Action 9 — Branch: Critérios do Evento Atendidos?

| Condição | Destino |
|----------|---------|
| `hs_event_criteria_met` = `"true"` | Action 10 (envio moradores) |
| Caso contrário | Fim ("Critérios de eventos não atendidos") |

---

## Action 10 — Custom Code: Envia E-mail aos Moradores

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `Hub_DB`, `automacao_hubspot` |

### Inputs

| Nome | Origem |
|------|--------|
| `outros_contatos_json` | Action 1 → `outros_contatos_json` |
| `protegidos` | Action 1 → `protegidos` |
| `indiciados` | Action 1 → `indiciados` |
| `ocorrencias` | Action 1 → `ocorrencias` |
| `proprietario_nome` | Action 1 → `proprietario_nome` |
| `wpp_ticket` | Action 1 → `wpp_ticket` |
| `email_ticket` | Action 1 → `email_ticket` |
| `endereco_logradouro` | Action 1 → `endereco_logradouro` |
| `link_botao` | Action 1 → `link_botao` |
| `template_moradores_id` | Action 1 → `template_moradores_id` |

### Outputs

| Nome | Tipo |
|------|------|
| `emails_enviados` | STRING |
| `erros` | STRING |

### Código Python

```python
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List

HUBSPOT_TOKEN = os.environ["Hub_DB"]

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

## IDs Importantes

| Item | ID |
|------|-----|
| Pipeline "Retenção" | `52153112` |
| Stage "Em tratativa" | `105781013` |
| HubDB Table ID (UF) | `224702045` |
| Local Object Type | `2-17828781` |
| Airtable Base ID | `app1uxxj9gL9otgrB` |
| Airtable Field (e-mail rep. legal) | `fldpy0Ufbxm9K4iKq` |
| Propriedade UF no ticket | `estado__ocorrencia_` |

---

## Data Sources (Associações configuradas no workflow)

| Nome | Objeto | Association Type ID | Categoria |
|------|--------|-------|-----------|
| `fetched_object_286679922` | Contacts (0-1) | 16 | HUBSPOT_DEFINED |
| `fetched_object_286679923` | Contacts (0-1) | 16 | HUBSPOT_DEFINED |
| `fetched_object_286679921` | Companies (0-2) | 339 | HUBSPOT_DEFINED |

---

## Diagrama de Relacionamento

```
TICKET (pipeline: Retenção 52153112)
  │  propriedades: estado__ocorrencia_, hubspot_owner_id
  │
  └── [associação] ──▶ LOCAL (2-17828781)
                           │  propriedades: endereco, endereco_, no_do_endereco
                           │
                           ├── [Airtable: Título = endereco]
                           │       └── e-mail representante legal → Modelo A (síndico)
                           │
                           └── [contatos associados ao local] → Modelo B (moradores)
```

---

## Observações

- O delay de 10 minutos antes da Ação 1 permite que todas as associações do ticket estejam completas
- O nome interno da propriedade UF no ticket é `estado__ocorrencia_` (confirmado via JSON)
- Se o owner do ticket estiver vazio ou não constar no mapeamento, o fallback é Isabella Beça
- `previa` é calculado no momento do envio dos moradores (D+15), não na criação do ticket
- Se o ticket nunca chegar em "Em tratativa" dentro de 60 dias (86400 min), o e-mail dos moradores não é enviado
- O workflow tem re-enrollment **desabilitado**
- Tickets com `tipo_de_retencao = "Proativa"` ou `motivo_do_cancelamento = "Inadimplente"` são excluídos do workflow
