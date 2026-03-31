# Workflow: [Negócio] - E-mail Renovação D+90

## Informações Gerais

| Campo | Valor |
|-------|-------|
| **Nome** | [Negócio] - E-mail Renovação D+90 |
| **Tipo** | PLATFORM_FLOW (Workflow de Negócio) |
| **Object Type ID** | 0-3 (Deals) |
| **Re-enrollment** | A definir |
| **Trigger** | Manual |

---

## Objetivo

Quando um negócio é **inscrito manualmente** no workflow:

1. Aguarda **10 minutos**
2. Consulta a **tabela HubDB** pela propriedade `estado` do negócio → dados de segurança do estado
3. Busca o **e-mail do síndico (decisor)** via Airtable: Local associado ao negócio → `endereco` → tabela `local` → e-mail representante legal
4. Busca os **contatos associados ao local** (moradores), excluindo o decisor
5. Envia **e-mail ao síndico** (template `209945233980`)
6. Envia **e-mail aos moradores** (template `209889079702`)

---

## Fluxo Visual

```
[TRIGGER] Inscrição manual no workflow
    │
    ▼
[DELAY] Aguardar 10 minutos
    │
    ▼
[AÇÃO 1] Custom Code: Busca HubDB + Airtable + Dados do Local
    - Lê "estado" do negócio
    - Consulta HubDB pela UF → protegidos, indiciados, ocorrencias
    - Busca Local associado ao negócio → lê "endereco", "endereco_", "no_do_endereco"
    - Busca no Airtable pelo endereco → e-mail do síndico
    - Busca no HubSpot o contato com esse e-mail → exclui dos moradores
    - Para cada local → busca contatos associados
    │
    ▼
[BRANCH] encontrado = "1"?
    │
    ├── SIM ──▶ [AÇÃO 2] Envia e-mail ao síndico + moradores
    │                │
    │                ▼
    │           [FIM]
    │
    └── NÃO ──▶ [FIM]
```

---

## Trigger

| Campo | Valor |
|-------|-------|
| **Tipo** | Manual |
| **Condição** | Inscrição manual pelo usuário |

---

## Delay — 10 minutos

| Campo | Valor |
|-------|-------|
| **Tipo** | SINGLE_CONNECTION (actionTypeId: 0-1) |
| **Delta** | 10 |
| **Unidade** | MINUTES |

---

## Ação 1 — Custom Code: Busca e Prepara Todos os Dados

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `Hub_DB`, `airtable_token` |

### Inputs

| Nome | Propriedade | Tipo |
|------|-------------|------|
| `deal_id` | `hs_object_id` | OBJECT_PROPERTY |
| `bairro_ocorrencia` | `bairro` | OBJECT_PROPERTY |

### Outputs

| Nome | Tipo |
|------|------|
| `encontrado` | STRING |
| `bairro_recebido` | STRING |
| `decisor_email` | STRING |
| `outros_contatos_json` | STRING |
| `protegidos` | STRING |
| `indiciados` | STRING |
| `ocorrencias` | STRING |
| `endereco_logradouro` | STRING |

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
HUBDB_TABLE_ID = "224700702"
AIRTABLE_BASE_ID = "app1uxxj9gL9otgrB"
AIRTABLE_TABLE = "local"
AIRTABLE_FIELD_EMAIL = "fldpy0Ufbxm9K4iKq"

LOCAL_OBJECT_TYPE = "2-17828781"

HS_HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

TEMPLATE_SINDICO_ID = 209945233980
TEMPLATE_MORADORES_ID = 209889079702


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
            uf_row = normalizar(row.get("values", {}).get("bairro", "") or "")
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
    deal_id = str(inputs.get("deal_id", "")).strip()
    uf = str(inputs.get("bairro_ocorrencia", "")).strip()

    # ── Locais associados ao negócio ───────────────────────────────────────────
    locais_ids = get_associacoes("deals", deal_id, LOCAL_OBJECT_TYPE) if deal_id else []

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

    # ── Busca HubDB pela UF ───────────────────────────────────────────────────
    protegidos = ""
    indiciados = ""
    ocorrencias = ""
    encontrado = "0"

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
            "bairro_recebido": uf,
            "decisor_email": decisor_email,
            "outros_contatos_json": json.dumps(outros_contatos_ids),
            "protegidos": protegidos,
            "indiciados": indiciados,
            "ocorrencias": ocorrencias,
            "endereco_logradouro": endereco_logradouro,
        }
    }
```

---

## Branch — UF Encontrada?

| Condição | Destino |
|----------|---------|
| `encontrado` = `"1"` | Ação 2 (envio de e-mails) |
| Caso contrário | Fim |

---

## Ação 2 — Custom Code: Envia E-mail ao Síndico + Moradores

### Configuração

| Campo | Valor |
|-------|-------|
| **Tipo** | CUSTOM_CODE |
| **Runtime** | Python 3.9 |
| **Secrets** | `Hub_DB` |

### Inputs

| Nome | Origem |
|------|--------|
| `decisor_email` | Ação 1 → `decisor_email` |
| `outros_contatos_json` | Ação 1 → `outros_contatos_json` |
| `protegidos` | Ação 1 → `protegidos` |
| `indiciados` | Ação 1 → `indiciados` |
| `ocorrencias` | Ação 1 → `ocorrencias` |
| `endereco_logradouro` | Ação 1 → `endereco_logradouro` |

### Outputs

| Nome | Tipo |
|------|------|
| `enviado_sindico` | STRING |
| `emails_moradores_enviados` | STRING |
| `erros` | STRING |

### Código Python

```python
import os
import json
import requests
from typing import Optional, List

HUBSPOT_TOKEN = os.environ["Hub_DB"]

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

TEMPLATE_SINDICO_ID = 209945233980
TEMPLATE_MORADORES_ID = 209889079702


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
    decisor_email = str(inputs.get("decisor_email", "")).strip()
    outros_json = inputs.get("outros_contatos_json", "[]")

    custom_props = {
        "protegidos":  inputs.get("protegidos", ""),
        "indiciados":  inputs.get("indiciados", ""),
        "ocorrencias": inputs.get("ocorrencias", ""),
        "endereco":    inputs.get("endereco_logradouro", ""),
    }

    try:
        parsed = json.loads(outros_json)
        outros_ids: List[str] = parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        outros_ids = []

    enviado_sindico = "0"
    enviados_moradores = 0
    erros = []

    # Envia e-mail ao síndico (decisor)
    if decisor_email:
        ok, motivo = enviar_email(decisor_email, TEMPLATE_SINDICO_ID, custom_props)
        if ok:
            enviado_sindico = "1"
        else:
            erros.append(f"decisor:{decisor_email}|{motivo}")

    # Envia e-mail aos moradores
    for cid in outros_ids:
        email = get_email_contato(cid)
        if not email:
            continue
        ok, motivo = enviar_email(email, TEMPLATE_MORADORES_ID, custom_props)
        if ok:
            enviados_moradores += 1
        else:
            erros.append(f"morador:{cid}|{motivo}")

    return {
        "outputFields": {
            "enviado_sindico": enviado_sindico,
            "emails_moradores_enviados": str(enviados_moradores),
            "erros": json.dumps(erros),
        }
    }
```

---

## Templates de E-mail

| Destinatário | Template ID |
|-------------|------------|
| Síndico (Decisor) | `209945233980` |
| Moradores | `209889079702` |

---

## IDs Importantes

| Item | ID |
|------|-----|
| HubDB Table ID (Bairro) | `224700702` |
| Local Object Type | `2-17828781` |
| Airtable Base ID | `app1uxxj9gL9otgrB` |
| Airtable Field (e-mail rep. legal) | `fldpy0Ufbxm9K4iKq` |
| Propriedade Bairro no negócio | `bairro` |

---

## Diagrama de Relacionamento

```
NEGÓCIO (Deal)
  │  propriedade: estado
  │
  └── [associação] ──▶ LOCAL (2-17828781)
                           │  propriedades: endereco, endereco_, no_do_endereco
                           │
                           ├── [Airtable: Título = endereco]
                           │       └── e-mail representante legal → Template Síndico
                           │
                           └── [contatos associados ao local] → Template Moradores
```

---

## Observações

- O delay de 10 minutos antes da Ação 1 permite que todas as associações do negócio estejam completas
- O nome interno da propriedade UF no negócio é `estado` — confirmar em Config > Propriedades > Negócios
- Se o local não tiver `endereco`, ou o Airtable não retornar resultado, `decisor_email` ficará vazio e o e-mail ao síndico não será enviado
- Ambos os e-mails (síndico + moradores) são enviados na mesma ação, sem espera entre eles
- O workflow é acionado manualmente — não há enrollment criteria automático
- Templates únicos para todas as UFs
