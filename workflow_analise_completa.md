# Análise Completa do Workflow HubSpot

## Informações Gerais

| Campo | Valor |
|-------|-------|
| **ID** | 1639643793 |
| **Nome** | Contato [Geral]: Garante informações únicas no contato |
| **Tipo** | CONTACT_FLOW (Workflow de Contato) |
| **Status** | Ativo (isEnabled: true) |
| **Criado em** | 2025-03-20T20:46:16.311Z |
| **Atualizado em** | 2025-12-22T19:36:21.318Z |
| **Revisão** | 112 |
| **Object Type ID** | 0-1 (Contatos) |

---

## Objetivo do Workflow

Este workflow garante a **integridade e unicidade dos dados de contato** no HubSpot, realizando:

1. **Validação de CPF** - Verifica se o documento é um CPF válido (algoritmo brasileiro)
2. **Formatação de Telefone** - Padroniza números para formato brasileiro (+55)
3. **Detecção de Duplicatas** - Busca contatos existentes com mesmo CPF, telefone ou email
4. **Merge Automático** - Funde contatos duplicados quando detectados
5. **Notificações Slack** - Alerta o time sobre erros e inconsistências

---

## Critérios de Enrollment (Triggers)

O workflow é **baseado em eventos** (`EVENT_BASED`) com **re-enrollment habilitado**.

### Eventos que Disparam o Workflow:

```json
{
  "shouldReEnroll": true,
  "type": "EVENT_BASED"
}
```

| Evento | Condição |
|--------|----------|
| Propriedade `email` alterada | Quando `hs_value` é conhecido |
| Propriedade `documento` alterada | Quando `hs_value` é conhecido |
| Propriedade `phone` alterada | Quando `hs_value` é conhecido |
| Evento 4-1463224 | Qualquer ocorrência (sem filtros) |

---

## Fluxo de Ações (Mapa Visual)

```
[START: Action 7] - Busca email do proprietário no HubSpot
       ↓
[Action 8] - Converte email para Slack User ID
       ↓
[Action 1] - Branch: Documento é conhecido?
       ├── SIM → [Action 3] - Valida CPF
       │            ↓
       │         [Action 4] - CPF válido?
       │            ├── TRUE → [Action 9] - Busca duplicatas por CPF
       │            │              ↓
       │            │           [Action 10] - Quantos contatos encontrados?
       │            │              ├── 0 → [GOTO Action 2]
       │            │              ├── 1 → [GOTO Action 2]
       │            │              └── >1 → [Action 11] - Alerta Slack (múltiplos CPFs)
       │            │
       │            └── FALSE → [Action 6] - Alerta Slack (CPF inválido)
       │                           ↓
       │                        [Action 5] - Limpa campo documento
       │
       └── NÃO → [Action 2] - Branch: Phone é conhecido?
                    ├── SIM → [Action 12] - Formata telefone
                    │            ↓
                    │         [Action 13] - Tipo de número?
                    │            ├── "Número inválido" → [Action 15] - Alerta Slack
                    │            │                          ↓
                    │            │                       [Action 14] - Limpa phone
                    │            │                          ↓
                    │            │                       [Action 35] - Limpa WhatsApp
                    │            │
                    │            ├── "Número fixo formatado" → [Action 39] - Alerta Slack
                    │            │                                ↓
                    │            │                             [Action 37] - Salva em telefone_fixo
                    │            │                                ↓
                    │            │                             [Action 36] - Limpa phone
                    │            │                                ↓
                    │            │                             [GOTO Action 19]
                    │            │
                    │            └── "Número celular formatado" → [Action 32] - Atualiza phone
                    │                                               ↓
                    │                                            [Action 34] - Atualiza WhatsApp
                    │                                               ↓
                    │                                            [Action 38] - Delay 1 min
                    │                                               ↓
                    │                                            [Action 16] - Busca duplicatas por phone
                    │                                               ↓
                    │                                            [Action 29] - Quantos encontrados?
                    │                                               ├── 0 → [GOTO Action 19]
                    │                                               ├── 1 → [Action 31] - Merge contatos
                    │                                               │          ↓
                    │                                               │       [Action 19]
                    │                                               └── >1 → [GOTO Action 19]
                    │
                    └── NÃO → [FIM]

[Action 19] - Branch: Email é conhecido?
       ├── SIM → [Action 20] - Busca duplicatas por email
       │            ↓
       │         [Action 21] - Quantos encontrados?
       │            ├── 0 → [FIM]
       │            ├── 1 → [Action 22] - Alerta Slack (múltiplos emails)
       │            └── Existe → [Action 26] - Consolida IDs
       │                           ↓
       │                        [Action 27] - IDs consistentes?
       │                           ├── 0 → [FIM]
       │                           ├── 1 → [Action 28] - Alerta Slack (inconsistência)
       │                           └── OK → [FIM]
       │
       └── NÃO → [FIM]
```

---

## Códigos Personalizados (Custom Code)

### Action 7: Busca Email do Proprietário

**Runtime:** Python 3.9
**Secrets:** `automacao_hubspot`

**Input:**
- `hubspot_owner_id` → Propriedade do contato

**Output:**
- `email_proprietario` → String

```python
import requests
import os

token = os.getenv("automacao_hubspot")

headers_hub = {
  "Authorization": f"Bearer {token}",
  "Content-Type": "application/json"
}

def main(event):
  
  id_usuario = event["inputFields"]["hubspot_owner_id"]
  
  url = f"https://api.hubapi.com/crm/v3/owners/{id_usuario}"
  
  payload = {
    'limit': 100
  }
  
  response = requests.get(url, headers=headers_hub, params=payload)
  print(response)
  data = response.json()
  
  email_proprietario = data['email']
  
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "email_proprietario": email_proprietario
    }
  }
```

**Lógica:**
1. Recebe o `hubspot_owner_id` do contato
2. Faz GET na API de Owners do HubSpot
3. Extrai e retorna o email do proprietário

---

### Action 8: Converte Email para Slack User ID

**Runtime:** Python 3.9
**Secrets:** `token_slack`

**Input:**
- `email_proprietario` → Output da Action 7

**Output:**
- `slack_proprietario` → String (Slack User ID)

```python
import requests
import os

def get_user_id_by_email(email):
  
  slack_token = os.getenv("token_slack")
  url = "https://slack.com/api/users.lookupByEmail"
  # Headers com o token de autorização
  headers = {
    "Authorization": f"Bearer {slack_token}"
  }
  # Parâmetros com o email do usuário
  params = {
    "email": email
  }
  # Envia a requisição para a API do Slack
  response = requests.get(url, headers=headers, params=params)
  # Verifica a resposta da API
  if response.status_code == 200:
    data = response.json()
    if data.get("ok"):
      # Retorna o ID do usuário
      return data["user"]["id"]
    else:
      print(f"Erro na resposta: {data.get('error')}")
      return None
  else:
    print(f"Erro na requisição: {response.status_code}")
    return None

def main(event):
  
  # O proprietario inicial só não sera igual ao vendedor da rota caso a rota esteja vazia ou tenham quebrado o processo de vendas fora da rota
  email_proprietario = event["inputFields"]["email_proprietario"]
  
  
  slack_proprietario = get_user_id_by_email(email_proprietario)
  
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "slack_proprietario": slack_proprietario,
    }
  }
```

**Lógica:**
1. Recebe o email do proprietário
2. Usa a API do Slack `users.lookupByEmail` para converter email → User ID
3. Retorna o Slack User ID para uso em menções (@usuario)

---

### Action 3: Validação de CPF

**Runtime:** Python 3.9
**Secrets:** Nenhum

**Input:**
- `documento` → Propriedade do contato

**Output:**
- `resposta_cpf` → Boolean (true/false como string)

```python
def valida_cpf(cpf):
  # Remove caracteres não numéricos
  cpf = ''.join(filter(str.isdigit, cpf))

  # Verifica se o CPF tem 11 dígitos
  if len(cpf) != 11:
      return False

  # Verifica se todos os dígitos são iguais
  if cpf == cpf[0] * 11:
      return False

  # Calcula o primeiro dígito verificador
  soma = 0
  for i in range(9):
      soma += int(cpf[i]) * (10 - i)
  resto = soma % 11
  digito1 = 11 - resto if resto > 1 else 0

  # Verifica se o primeiro dígito verificador está correto
  if digito1 != int(cpf[9]):
      return False

  # Calcula o segundo dígito verificador
  soma = 0
  for i in range(10):
      soma += int(cpf[i]) * (11 - i)
  resto = soma % 11
  digito2 = 11 - resto if resto > 1 else 0

  # Verifica se o segundo dígito verificador está correto
  if digito2 != int(cpf[10]):
      return False

  # Se todas as verificações passaram, o CPF é válido
  return True

def main(event):
    
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  cpf = event["inputFields"]["documento"]
  
  resposta_cpf = valida_cpf(cpf)
  
  # Exemplo de uso
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "resposta_cpf": resposta_cpf
    }
  }
```

**Lógica do Algoritmo de Validação CPF:**
1. Remove caracteres não numéricos (pontos, traços)
2. Verifica se tem exatamente 11 dígitos
3. Rejeita CPFs com todos dígitos iguais (111.111.111-11, etc.)
4. Calcula o primeiro dígito verificador usando módulo 11
5. Calcula o segundo dígito verificador usando módulo 11
6. Compara os dígitos calculados com os informados

---

### Action 12: Formatação de Telefone Brasileiro

**Runtime:** Python 3.9
**Secrets:** Nenhum

**Input:**
- `telefone` → Propriedade `phone` do contato

**Output:**
- `telefone_formatado` → String (formato +55XXXXXXXXXXX)
- `telefone_validacao` → String ("Número celular formatado", "Número fixo formatado", "Número inválido")

```python
import re

def format_phone(phone: str):
    # Removendo caracteres não numéricos
    phone = re.sub(r"\D", "", phone)
    
    # Verificando se tem código do Brasil (55) e removendo se necessário
    if phone.startswith("55") and len(phone) == 12:
        phone = phone[2:]  # Remover o código do país (+55)
    
    # Verificando se tem código do Brasil (55) e tem 13 dígitos (número com DDD)
    elif phone.startswith("55") and len(phone) == 13:
        phone = phone[2:]  # Remover o código do país (+55)
    
    # Verificando se o número é composto apenas por dígitos repetidos
    if len(set(phone)) == 1:  # Se todos os caracteres são iguais
        return {"formattedPhone": '', "error": "Número inválido"}

    # Verificando se o número é celular (11 dígitos e o segundo dígito é 9)
    if len(phone) == 11 and phone[2] == "9":
        formatted_phone = f"+55{phone}"
        return {"formattedPhone": formatted_phone, "error": "Número celular formatado"}

    # Verificando se o número é fixo (10 dígitos ou 8 dígitos)
    if len(phone) == 10:
        # DDDs válidos para números fixos (sem considerar DDDs de celulares)
        valid_ddds_fixo = ["11", "12", "13", "14", "15", "16", "17", "18", "19", 
    "21", "22", "24", "27", "28", "31", "32", "33", "34", 
    "35", "37", "38", "41", "42", "43", "44", "45", "46", 
    "47", "48", "49", "51", "52", "53", "54", "55", "61", 
    "62", "63", "64", "65", "66", "67", "68", "69", "71", 
    "73", "74", "75", "77", "78", "79", "81", "82", "83", 
    "84", "85", "86", "87", "88", "89", "91", "92", "93", 
    "94", "95", "96", "97", "98", "99"]
        
        # Verificando o DDD de números fixos válidos
        ddd = phone[:2]
        
        if ddd in valid_ddds_fixo:
            formatted_phone = f"+55{phone}"
            return {"formattedPhone": formatted_phone, "error": "Número fixo formatado"}
        
        return {"formattedPhone": '', "error": "Número inválido"}

    if len(phone) == 8:
        # Não formatamos o número fixo com 8 dígitos, apenas retornamos
        return {"formattedPhone": phone, "error": "Número fixo formatado"}

    # Caso o número não se encaixe nas regras
    return {"formattedPhone": '', "error": "Número inválido"}


def main(event):
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  telefone = str(event["inputFields"]["telefone"])
  
  print(telefone)
  
  formatacao = format_phone(telefone)
  
  telefone_formatado = formatacao.get('formattedPhone')
  telefone_validacao = formatacao.get('error')
  
  print(formatacao)
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "telefone_formatado": telefone_formatado,
      "telefone_validacao": telefone_validacao
    }
  }
```

**Lógica de Formatação:**
1. Remove todos caracteres não numéricos
2. Remove código do país (+55) se já presente
3. Rejeita números com todos dígitos iguais
4. **Celular:** 11 dígitos com 9 na terceira posição → Formata como +55XXXXXXXXXXX
5. **Fixo:** 10 dígitos com DDD válido → Formata como +55XXXXXXXXXX
6. **Fixo sem DDD:** 8 dígitos → Retorna sem formatação
7. Outros casos → Retorna como inválido

---

### Action 9: Busca Duplicatas por CPF

**Runtime:** Python 3.9
**Secrets:** `automacao_hubspot`

**Input:**
- `documento` → Propriedade do contato

**Output:**
- `id_contato_cpf` → String ("0" = não encontrado, "1" = múltiplos, ou ID do contato)

```python
import requests
import os

token = os.getenv("automacao_hubspot")

headers_hub = {
  "authorization": f"Bearer {token}"
}

def main(event):
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  cpf = event["inputFields"]["documento"]
  
  url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
  
  payload_cpf = {
    "properties": ["hs_object_id"],
    "limit":100,
    "filterGroups": [
      {
        "filters":[
          {
            "propertyName": "documento",
            "operator": "EQ",
            "value": cpf
          }
        ]
      }
    ]
  }
  
  response_cpf = requests.post(url,headers=headers_hub,json=payload_cpf)
  
  data_cpf = response_cpf.json()
  print(data_cpf)
  total_cpf = data_cpf.get('total')
  info_cpf = data_cpf.get('results')
  
  if total_cpf == 1:
    id_contato_cpf = str(info_cpf[0].get('id'))
  elif total_cpf > 1:
    id_contato_cpf = "1"
  else:
    id_contato_cpf = "0"
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "id_contato_cpf": id_contato_cpf
    }
  }
```

**Lógica:**
1. Busca contatos com o mesmo CPF usando Search API
2. Retorna:
   - `"0"` se nenhum encontrado
   - `"1"` se múltiplos encontrados (flag de erro)
   - ID do contato se exatamente 1 encontrado

---

### Action 16: Busca Duplicatas por Telefone

**Runtime:** Python 3.9
**Secrets:** `automacao_hubspot`

**Input:**
- `phone` → Output da Action 12 (`telefone_formatado`)

**Output:**
- `id_contato_phone` → String ou Lista de IDs
- `total_phone` → Number

```python
import requests
import os

token = os.getenv("automacao_hubspot")

headers_hub = {
  "authorization": f"Bearer {token}"
}

def main(event):
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  phone = event["inputFields"]["phone"]
  
  url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
  
  payload_cpf = {
    "properties": ["hs_object_id"],
    "limit":100,
    "filterGroups": [
      {
        "filters":[
          {
            "propertyName": "phone",
            "operator": "EQ",
            "value": phone
          }
        ]
      }
    ]
  }
  
  response_phone = requests.post(url,headers=headers_hub,json=payload_cpf)
  
  data_phone = response_phone.json()
  print(data_phone)
  total_phone = data_phone.get('total')
  info_phone = data_phone.get('results')
  
  if total_phone == 1:
    id_contato = str(info_phone[0].get('id'))
  elif total_phone > 1:
    id_contato = [str(item.get('id')) for item in info_phone]
  else:
    id_contato = "0"
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "id_contato_phone": id_contato,
      "total_phone": total_phone
    }
  }
```

**Lógica:**
1. Busca contatos com o mesmo telefone
2. Retorna:
   - `"0"` se nenhum encontrado
   - ID único se 1 encontrado
   - **Lista de IDs** se múltiplos encontrados (para merge)

---

### Action 20: Busca Duplicatas por Email

**Runtime:** Python 3.9
**Secrets:** `automacao_hubspot`

**Input:**
- `email` → Propriedade do contato

**Output:**
- `id_contato_email` → String

```python
import requests
import os

token = os.getenv("automacao_hubspot")

headers_hub = {
  "authorization": f"Bearer {token}"
}

def main(event):
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  email = event["inputFields"]["email"]
  
  url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
  
  payload_email = {
    "properties": ["hs_object_id"],
    "limit":100,
    "filterGroups": [
      {
        "filters":[
          {
            "propertyName": "email",
            "operator": "EQ",
            "value": email
          }
        ]
      }
    ]
  }
  
  response_email = requests.post(url,headers=headers_hub,json=payload_email)
  
  data_email = response_email.json()
  print(data_email)
  total_email = data_email.get('total')
  info_email = data_email.get('results')
  
  if total_email == 1:
    id_contato_email = str(info_email[0].get('id'))
  elif total_email > 1:
    id_contato_email = "1"
  else:
    id_contato_email = "0"
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "id_contato_email": id_contato_email
    }
  }
```

---

### Action 26: Consolidação de IDs (Cross-Reference)

**Runtime:** Python 3.9
**Secrets:** `automacao_hubspot`

**Input:**
- `id_contato_email` → Output da Action 20
- `id_contato_phone` → Output da Action 16
- `id_contato_cpf` → Output da Action 9

**Output:**
- `id_contato` → String ("0" = novo, "1" = inconsistência, ou ID consolidado)

```python
def main(event):
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  id_contato_email = event["inputFields"].get("id_contato_email", "0")
  
  id_contato_telefone = event["inputFields"].get("id_contato_phone", "0")
  
  id_contato_cpf = event["inputFields"].get("id_contato_cpf", "0")
  
  if id_contato_cpf == "0" and id_contato_telefone == "0" and id_contato_email == "0":
    id_contato = "0"
  elif id_contato_cpf == "0" and id_contato_telefone == "0" and id_contato_email != "0":
    id_contato = id_contato_email
  elif id_contato_cpf == "0" and id_contato_telefone != "0" and id_contato_email == "0":
    id_contato = id_contato_telefone
  elif id_contato_cpf != "0" and id_contato_telefone == "0" and id_contato_email == "0":
    id_contato = id_contato_cpf
  elif id_contato_cpf != "0" and id_contato_telefone != "0" and id_contato_email == "0":
    if id_contato_cpf == id_contato_telefone:
      id_contato = id_contato_cpf
    else:
      id_contato = "1"
  elif id_contato_cpf != "0" and id_contato_telefone == "0" and id_contato_email != "0":
    if id_contato_cpf == id_contato_email:
      id_contato = id_contato_email
    else:
      id_contato = "1"
  elif id_contato_cpf == "0" and id_contato_telefone != "0" and id_contato_email != "0":
    if id_contato_telefone == id_contato_email:
      id_contato = id_contato_telefone
    else:
      id_contato = "1"
  else:
    if id_contato_cpf == id_contato_telefone and id_contato_cpf == id_contato_email:
      id_contato = id_contato_cpf
    else:
      id_contato = "1"  
  
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "id_contato": id_contato
    }
  }
```

**Lógica de Consolidação (Matriz de Decisão):**

| CPF | Phone | Email | Resultado |
|-----|-------|-------|-----------|
| 0 | 0 | 0 | "0" (contato novo) |
| 0 | 0 | X | id_email |
| 0 | X | 0 | id_phone |
| X | 0 | 0 | id_cpf |
| X | X | 0 | id_cpf SE igual, senão "1" |
| X | 0 | X | id_cpf SE igual, senão "1" |
| 0 | X | X | id_phone SE igual, senão "1" |
| X | X | X | id_cpf SE todos iguais, senão "1" |

**"1" = Inconsistência detectada** (mesmo dado em contatos diferentes)

---

### Action 31: Merge de Contatos Duplicados

**Runtime:** Python 3.9
**Secrets:** `automacao_hubspot`

**Input:**
- `id_contato` → Lista de IDs (string representation)

**Output:**
- `final_contact_id` → String (ID do contato final após merge)

```python
import requests
import json
import ast
import os

token = os.getenv("automacao_hubspot")
print(token)

def merge_contacts(object_id_to_merge, primary_object_id):
  # URL para o merge de contatos
  url = "https://api.hubapi.com/crm/v3/objects/contacts/merge"
  
  # Cabeçalhos necessários
  headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
  }
  
  # Dados para o merge no formato JSON
  data = {
    "objectIdToMerge": object_id_to_merge,
    "primaryObjectId": primary_object_id
  }
  # Fazendo a requisição POST
  response = requests.post(url, headers=headers, data=json.dumps(data))
  
  # Verificando o status da resposta
  if response.status_code == 200:
    # Retorna o ID do novo contato após o merge
    merged_contact = response.json()
    return merged_contact['id']
  else:
    print(f"Erro ao realizar o merge: {response.status_code}")
    return None

def sequential_merge(contact_ids):
  # Começa com o primeiro contato da lista como o contato principal
  primary_contact_id = contact_ids[0]
  
  # Realiza o merge sequencial entre os contatos
  for contact_id in contact_ids[1:]:
    primary_contact_id = merge_contacts(primary_contact_id, contact_id)
    if not primary_contact_id:
      print("Erro ao fundir contatos.")
      return None
    
  return primary_contact_id      
      
def main(event):
  # Use entradas para obter dados de qualquer ação em seu fluxo de trabalho e use-os em seu código em vez de usar a API da HubSpot.
  id_contato_ = event["inputFields"]["id_contato"]
  id_contato = ast.literal_eval(id_contato_)
  
  final_contact_id = sequential_merge(id_contato)
  # Retorne os dados de saída que podem ser usados ​​em ações posteriores em seu fluxo de trabalho.
  return {
    "outputFields": {
      "final_contact_id": final_contact_id
    }
  }
```

**Lógica de Merge Sequencial:**
1. Converte a string de lista em lista Python (`ast.literal_eval`)
2. Usa o primeiro contato como "principal"
3. Itera pelos demais, fazendo merge um a um
4. Cada merge usa a API `POST /crm/v3/objects/contacts/merge`
5. Retorna o ID final do contato consolidado

---

## Ações de Atualização de Propriedades

### Action 5: Limpa Documento (CPF Inválido)
```json
{
  "property_name": "documento",
  "value": ""
}
```

### Action 14: Limpa Phone (Telefone Inválido)
```json
{
  "property_name": "phone",
  "value": ""
}
```

### Action 32: Atualiza Phone com Formato Correto
```json
{
  "property_name": "phone",
  "value": "{Action 12 → telefone_formatado}"
}
```

### Action 34: Atualiza WhatsApp
```json
{
  "property_name": "hs_whatsapp_phone_number",
  "value": "{Action 12 → telefone_formatado}"
}
```

### Action 35: Limpa WhatsApp
```json
{
  "property_name": "hs_whatsapp_phone_number",
  "value": ""
}
```

### Action 36: Limpa Phone (Número Fixo)
```json
{
  "property_name": "phone",
  "value": ""
}
```

### Action 37: Salva Telefone Fixo
```json
{
  "property_name": "numero_de_telefone_fixo",
  "value": "{Action 12 → telefone_formatado}"
}
```

---

## Notificações Slack

**Canal:** `C08JR4FR5M1`

### Action 6: CPF Inválido
```
*Erro:* O número de CPF adicionado é inválido.

*CPF adicionado:* {{ enrolled_object.documento }}

*Ação:* O número do documento foi excluído, devemos corrigir direto no contato.

*Link do contato:* https://app.hubspot.com/contacts/23636141/record/0-1/{{ enrolled_object.hs_object_id }}

Vendedor responsável: <@{{ action_outputs.action_output_8.slack_proprietario }}>
```

### Action 11: Múltiplos Contatos com Mesmo CPF
```
*Erro:* Existem diversos contatos criados com o mesmo CPF.

*CPF adicionado:* {{ enrolled_object.documento }}

*Ação:* O time de <!subteam^S06E1D2TWF2> irá corrigir.

*Link do contato:* https://app.hubspot.com/contacts/23636141/record/0-1/{{ enrolled_object.hs_object_id }}

Vendedor responsável: <@{{ action_outputs.action_output_8.slack_proprietario }}>
```

### Action 15: Telefone Inválido
```
*Erro:* O número adicionado para o "Número de Telefone" é inválido.

*Número do Telefone Adicionado:* {{ enrolled_object.phone }}

*Ação:* O telefone esta sendo apagado e deve ser corrigido no negócio.

*Link do negócio:* https://app.hubspot.com/contacts/23636141/record/0-3/{{ enrolled_object.hs_object_id }}

Vendedor responsável: <@{{ action_outputs.action_output_8.slack_proprietario }}>
```

### Action 22: Múltiplos Contatos com Mesmo Telefone
```
Existem diversos contatos com o Telefone.

Telefone: {{ enrolled_object.phone }}

<!subteam^S06E1D2TWF2> revisar a base com urgência.
```

### Action 28: Inconsistência entre CPF/Email/Telefone
```
*Erro:* Ao validar as informações para o representante legal 

1. Email
2. Telefone
3. CPF

Constatamos de que existem diferentes contatos com algumas dessas informações.

*CPF Adicionado:* {{ enrolled_object.documento }}
*Email Adicionado:* {{ enrolled_object.email }}
*Telefone Adicionado:* {{ enrolled_object.phone }}

*Ação:* O contato não foi criado o time de <!subteam^S06E1D2TWF2> deve analisar o caso.

*Link do negócio:* https://app.hubspot.com/contacts/23636141/record/0-3/{{ enrolled_object.hs_object_id }}

Vendedor responsável: <@{{ action_outputs.action_output_8.slack_proprietario }}>
```

### Action 39: Telefone Fixo Detectado
```
*Erro:* O número adicionado para o "Número de Telefone" é um número fixo.

*Número do Telefone Adicionado:* {{ enrolled_object.phone }}

*Ação:* Apagamos o valor no campo de número de telefone e cadastramos no campo de telefone fixo

*Link do negócio:* https://app.hubspot.com/contacts/23636141/record/0-3/{{ enrolled_object.hs_object_id }}

Vendedor responsável: <@{{ action_outputs.action_output_8.slack_proprietario }}>
```

---

## Propriedades Utilizadas

### Propriedades de Entrada (do Contato)
| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| `documento` | String | CPF do contato |
| `phone` | String | Número de telefone |
| `email` | String | Email do contato |
| `hubspot_owner_id` | Number | ID do proprietário do contato |
| `hs_object_id` | Number | ID interno do contato |

### Propriedades Atualizadas pelo Workflow
| Propriedade | Ação |
|-------------|------|
| `documento` | Limpa se CPF inválido |
| `phone` | Atualiza com formato +55 ou limpa |
| `hs_whatsapp_phone_number` | Sincroniza com phone formatado |
| `numero_de_telefone_fixo` | Recebe telefones fixos |

---

## Secrets Utilizados

| Secret | Usado em | Propósito |
|--------|----------|-----------|
| `automacao_hubspot` | Actions 7, 9, 16, 20, 26, 31 | Token Bearer para API HubSpot |
| `token_slack` | Action 8 | Token para API Slack |

---

## Integrações Externas

### HubSpot API
- `GET /crm/v3/owners/{id}` - Busca dados do proprietário
- `POST /crm/v3/objects/contacts/search` - Busca contatos duplicados
- `POST /crm/v3/objects/contacts/merge` - Merge de contatos

### Slack API
- `GET /users.lookupByEmail` - Converte email para User ID
- Mensagens para canal `C08JR4FR5M1`
- Menção a grupo `<!subteam^S06E1D2TWF2>`

---

## Pontos de Atenção e Melhorias Potenciais

### Riscos Identificados

1. **Sem tratamento de erro nas APIs** - Se a API do HubSpot ou Slack falhar, o workflow pode quebrar silenciosamente

2. **Delay fixo de 1 minuto** (Action 38) - Pode não ser suficiente em casos de alta latência

3. **Limite de 100 resultados** nas buscas - Pode perder duplicatas se houver mais de 100

4. **ast.literal_eval** no Action 31 - Risco de segurança se input não sanitizado

5. **Mensagens Slack apontam para "negócio"** mas workflow é de contato

### Sugestões de Melhoria

1. Adicionar try/except em todos os códigos customizados
2. Implementar retry logic para chamadas de API
3. Usar paginação na busca de duplicatas
4. Validar inputs antes de processar
5. Corrigir textos das mensagens Slack (contato vs negócio)
6. Adicionar logging estruturado para debugging

---

## JSON Original Completo

Para referência, o JSON completo do workflow está disponível na requisição:

```
GET https://api.hubapi.com/automation/v4/flows/1639643793
Authorization: Bearer {token}
```
