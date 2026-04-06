# Panorama de Segurança — Fluxo N8N (Parte 2)

## 5. Fluxo N8N — Arquitetura Nó a Nó

### Diagrama do Fluxo

```
[1. Webhook HubSpot]
        │
        ▼
[2. Extrair CEP + Número]
        │
        ▼
[3. Set Status = "processando" no HubSpot]
        │
        ▼
[4. Geocodificar: ViaCEP → lat/lon]
        │
        ▼
[5. Autenticar no Metabase]
        │
        ▼
[6. Consultar Ocorrências por Rua]──► threshold atingido? ──SIM──► [10. Consultar Desfechos]
        │                                                              │
        NÃO                                                            │
        ▼                                                              │
[7. Consultar Ocorrências Ruas Próximas (500m)]──► threshold? ─SIM─►──┤
        │                                                              │
        NÃO                                                            │
        ▼                                                              │
[8. Consultar Ocorrências por Bairro]──► threshold? ──────────SIM──►──┤
        │                                                              │
        NÃO                                                            │
        ▼                                                              │
[8b. Consultar Ocorrências Vizinhança (3km)]──► threshold? ───SIM──►──┤
        │                                                              │
        NÃO                                                            │
        ▼                                                              │
[9. Consultar Ocorrências por Zona (fallback)]─────────────────────►──┤
                                                                       │
                                                                       ▼
                                                              [10. Consultar Desfechos]
                                                                       │
                                                                       ▼
                                                              [11. Consultar Câmeras]
                                                                       │
                                                                       ▼
                                                              [12. Montar dados consolidados]
                                                                       │
                                                         ┌─────────────┼─────────────┐
                                                         ▼             ▼             ▼
                                                  [13. Gerar    [14. Gerar    [15. Upload
                                                   Template]    Resumo IA]    Storage]
                                                         │             │             │
                                                         └─────────────┼─────────────┘
                                                                       ▼
                                                              [16. Atualizar Lead HubSpot]
                                                                       │
                                                                       ▼
                                                              [17. Notificar pré-vendedor]
```

---

### Detalhamento dos Nós

#### Nó 1: Webhook Trigger (HubSpot Form Submission)
- **Tipo:** Webhook
- **Trigger:** HubSpot envia webhook quando formulário é submetido
- **Configuração no HubSpot:** Workflow que dispara ao criar Lead com CEP preenchido
- **Dados recebidos:** `lead_id`, `cep`, `numero_endereco`, `nome`, `email`

#### Nó 2: Extrair e Validar Dados
- **Tipo:** Code (JavaScript)
- **Lógica:**
```javascript
const cep = $input.first().json.cep.replace(/\D/g, '');
const numero = $input.first().json.numero_endereco || '';
const leadId = $input.first().json.lead_id;

if (!cep || cep.length !== 8) {
  throw new Error(`CEP inválido: ${cep}`);
}

return [{
  json: { cep, numero, leadId }
}];
```

#### Nó 3: Atualizar Status HubSpot → "processando"
- **Tipo:** HTTP Request
- **Método:** PATCH
- **URL:** `https://api.hubapi.com/crm/v3/objects/0-136/{{leadId}}`
- **Headers:** `Authorization: Bearer {{hubspot_token}}`
- **Body:**
```json
{
  "properties": {
    "panorama_status": "processando"
  }
}
```

#### Nó 4: Geocodificação (CEP + Número → Lat/Lon)
- **Tipo:** HTTP Request (2 chamadas sequenciais)

**4a. ViaCEP — obter endereço completo:**
```
GET https://viacep.com.br/ws/{{cep}}/json/
→ Retorna: logradouro, bairro, localidade (cidade), uf
```

**4b. Nominatim/OpenStreetMap — obter lat/lon:**
```
GET https://nominatim.openstreetmap.org/search?
    street={{numero}} {{logradouro}}&
    city={{localidade}}&
    state={{uf}}&
    country=Brazil&
    format=json&
    limit=1
→ Retorna: lat, lon
```

**Alternativa recomendada (mais precisa):** Google Geocoding API
```
GET https://maps.googleapis.com/maps/api/geocode/json?
    address={{numero}}+{{logradouro}},+{{localidade}},+{{uf}},+Brasil&
    key={{google_api_key}}
```

**Nota:** Nominatim é gratuito e sem limite, mas tem rate limit de 1 req/seg. Para o volume de leads inbound, é suficiente. Se precisar de mais precisão, Google Geocoding (US$5/1000 requests) é a melhor opção.

#### Nó 5: Autenticar no Metabase
- **Tipo:** HTTP Request
- **Método:** POST
- **URL:** `https://dados.gabriel.com.br/api/session`
- **Body:**
```json
{
  "username": "{{metabase_user}}",
  "password": "{{metabase_pass}}"
}
```
- **Output:** `session_token`

**Otimização:** Cachear o token em uma variável global do N8N e só renovar quando expirar (retorno 401).

#### Nó 6: Consultar Ocorrências (Camada Rua)
- **Tipo:** HTTP Request
- **Método:** POST
- **URL:** `https://dados.gabriel.com.br/api/dataset`
- **Headers:** `X-Metabase-Session: {{session_token}}`
- **Body:**
```json
{
  "database": 10,
  "type": "native",
  "native": {
    "query": "SELECT idticket, tipocrime, bairro, estado, cidade, endereco, zona, latitude, longitude, dataocorrencia, horario, pessoasindiciadas, tiposolicitante, tiporegistro FROM reports.ocorrencia WHERE efetividadeanalise = 'Efetiva' AND LOWER(endereco) LIKE LOWER('%{{rua_normalizada}}%') AND LOWER(cidade) = LOWER('{{cidade}}') AND (dataocorrencia < '2025-07-01' OR tiporegistro IN ('Ofício', 'Procedimento'))",
    "template-tags": {}
  }
}
```

**Nó 6b: Checar Threshold**
- **Tipo:** IF
- **Condição:** `ocorrencias.length >= 5`
  - SIM → Define `camada = "rua"` → Vai para Nó 10
  - NÃO → Vai para Nó 7

#### Nó 7: Consultar Ocorrências (Ruas Próximas — 500m)
- **Tipo:** HTTP Request + Code
- **Query SQL:** Busca todas ocorrências da cidade e filtra por distância no Code node

```sql
SELECT idticket, tipocrime, bairro, estado, cidade, endereco, zona,
       latitude, longitude, dataocorrencia, horario, pessoasindiciadas,
       tiposolicitante, tiporegistro
FROM reports.ocorrencia
WHERE efetividadeanalise = 'Efetiva'
  AND LOWER(bairro) = LOWER('{{bairro}}')
  AND (dataocorrencia < '2025-07-01' OR tiporegistro IN ('Ofício', 'Procedimento'))
```

**Filtro por distância (Code node):**
```javascript
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 +
            Math.cos(lat1 * Math.PI/180) * Math.cos(lat2 * Math.PI/180) *
            Math.sin(dLon/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

const leadLat = $input.first().json.lat;
const leadLon = $input.first().json.lon;

// Converte coordenadas do formato "23.56201770° S" → -23.56201770
function parseCoord(str) {
  if (!str) return null;
  const match = str.match(/([\d.]+)°?\s*([NSEW])/);
  if (!match) return parseFloat(str);
  let val = parseFloat(match[1]);
  if (match[2] === 'S' || match[2] === 'W') val = -val;
  return val;
}

const nearby = items.filter(item => {
  const lat = parseCoord(item.json.latitude);
  const lon = parseCoord(item.json.longitude);
  if (!lat || !lon) return false;
  return haversineKm(leadLat, leadLon, lat, lon) <= 0.5; // 500m
});

return [{ json: { ocorrencias: nearby, count: nearby.length } }];
```

- **Threshold:** `count >= 10` → camada = "ruas_proximas"

#### Nó 8: Consultar por Bairro
- **Query:** Mesma query do Nó 7, sem filtro de distância (usa todos do bairro)
- **Threshold:** `count >= 15`
- **Camada:** "bairro"

#### Nó 8b: Consultar Vizinhança (3km)
- **Query:** Busca todos os bairros da cidade, agrupa por bairro, calcula centróide de cada bairro e filtra os que estão a ≤3km do bairro do lead
- **Threshold:** `count >= 25`
- **Camada:** "vizinhanca"

#### Nó 9: Fallback — Zona
- **Query:**
```sql
SELECT * FROM reports.ocorrencia
WHERE efetividadeanalise = 'Efetiva'
  AND LOWER(zona) = LOWER('{{zona}}')
  AND (dataocorrencia < '2025-07-01' OR tiporegistro IN ('Ofício', 'Procedimento'))
```
- **Sem threshold mínimo** — sempre usa os dados disponíveis
- **Camada:** "zona"

#### Nó 10: Consultar Desfechos (mesma camada selecionada)
- **Tipo:** HTTP Request
- **Query SQL ajustada à camada selecionada:**
  - Rua: `WHERE LOWER(logradouro) LIKE LOWER('%{{rua}}%') AND LOWER(cidade) = LOWER('{{cidade}}')`
  - Bairro: `WHERE LOWER(bairro) = LOWER('{{bairro}}')`
  - Zona: `WHERE LOWER(zona) = LOWER('{{zona}}')`
- **Campos:** Total de indiciados, prisões em flagrante, tipos de desfecho

#### Nó 11: Consultar Câmeras Ativas (mesma camada)
- **Tipo:** HTTP Request
- **Query:**
```sql
SELECT COUNT(*) as total_cameras
FROM reports.eventoitemassinatura
WHERE situacao = 'Ativo'
  AND LOWER(bairro) = LOWER('{{bairro}}')
```
- **Nota:** Se camada = Rua ou Ruas Próximas, usar o bairro correspondente (câmeras não têm granularidade de rua)

#### Nó 12: Consolidar Dados
- **Tipo:** Code (JavaScript)
- **Monta o objeto final:**
```javascript
const dados = {
  camada: $input.first().json.camada,
  regiao_nome: $input.first().json.regiao_nome,
  // Dados gerais
  total_ocorrencias: ocorrencias.length,
  total_desfechos: desfechos.length,
  total_indiciados: desfechos.reduce((sum, d) => sum + (d.qtd_indiciados || 0), 0),
  total_prisoes_flagrante: desfechos.filter(d => d.houve_prisao === 'Sim').length,
  total_cameras: cameras.total_cameras,
  // Top 5 crimes
  top_crimes: Object.entries(
    ocorrencias.reduce((acc, o) => {
      acc[o.tipocrime] = (acc[o.tipocrime] || 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]).slice(0, 5),
  // Crime mais comum
  crime_mais_comum: null, // será preenchido pelo top_crimes[0]
  // Dados temporais (7, 15, 30 dias)
  resumo_7d: filtrarPorDias(ocorrencias, desfechos, 7),
  resumo_15d: filtrarPorDias(ocorrencias, desfechos, 15),
  resumo_30d: filtrarPorDias(ocorrencias, desfechos, 30),
  // Periodo geral
  periodo_inicio: '2023',
  periodo_fim: 'hoje'
};
```

---

## 6. Geração do Resumo Temporal (IA)

### Nó 14: Claude API — Gerar Resumo para Speech

- **Tipo:** HTTP Request
- **URL:** `https://api.anthropic.com/v1/messages`
- **Model:** `claude-haiku-4-5-20251001` (rápido e barato para geração estruturada)

#### System Prompt (com guardrails):
```
Você é um assistente de dados da Gabriel Segurança. Sua função é gerar resumos
factuais baseados EXCLUSIVAMENTE nos dados fornecidos.

REGRAS OBRIGATÓRIAS:
1. NUNCA invente dados, números ou eventos que não estejam nos dados fornecidos
2. NUNCA faça inferências, previsões ou especulações sobre tendências
3. NUNCA use linguagem sensacionalista ou alarmista
4. Use APENAS os números exatos dos dados fornecidos
5. Se não houver dados para um período, diga "Sem registros no período"
6. Formate o resumo para leitura rápida do pré-vendedor
7. Use o nome da região (bairro/zona) conforme fornecido
8. Mantenha tom profissional e objetivo
9. Inclua APENAS: contagem de ocorrências, tipos de crime, desfechos e períodos
10. NUNCA sugira que a região é "perigosa" ou "segura" — apresente apenas fatos
```

#### User Prompt:
```
Gere um resumo temporal para o pré-vendedor com base nos dados abaixo.
O resumo deve cobrir 3 períodos: últimos 7 dias, 15 dias e 30 dias.

Região: {{regiao_nome}} (camada: {{camada}})

DADOS ÚLTIMOS 7 DIAS:
- Ocorrências: {{resumo_7d.total_ocorrencias}}
- Tipos: {{resumo_7d.crimes_por_tipo}}
- Desfechos (indiciamentos): {{resumo_7d.total_desfechos}}
- Prisões em flagrante: {{resumo_7d.prisoes_flagrante}}

DADOS ÚLTIMOS 15 DIAS:
- Ocorrências: {{resumo_15d.total_ocorrencias}}
- Tipos: {{resumo_15d.crimes_por_tipo}}
- Desfechos: {{resumo_15d.total_desfechos}}
- Prisões em flagrante: {{resumo_15d.prisoes_flagrante}}

DADOS ÚLTIMOS 30 DIAS:
- Ocorrências: {{resumo_30d.total_ocorrencias}}
- Tipos: {{resumo_30d.crimes_por_tipo}}
- Desfechos: {{resumo_30d.total_desfechos}}
- Prisões em flagrante: {{resumo_30d.prisoes_flagrante}}
- Ruas mais afetadas: {{resumo_30d.ruas_top3}}
- Horários de maior incidência: {{resumo_30d.horarios_top3}}

Formate como resumo estruturado com marcadores, pronto para copy-paste.
```

#### Guardrails adicionais (validação pós-IA):
- **Nó Code após a IA:** Verifica se o resumo contém apenas números que existem nos dados de entrada. Se detectar discrepância > 10%, rejeita e usa template fixo com os dados brutos.

```javascript
// Validação pós-IA: extrair números do resumo e comparar com input
const resumo = $input.first().json.resumo_ia;
const dados = $input.first().json.dados_input;

const numerosNoResumo = resumo.match(/\d+/g).map(Number);
const numerosValidos = [
  dados.resumo_7d.total_ocorrencias,
  dados.resumo_15d.total_ocorrencias,
  dados.resumo_30d.total_ocorrencias,
  dados.total_desfechos,
  dados.total_indiciados,
  dados.total_prisoes_flagrante,
  // ... todos os números dos dados
];

const numerosDesconhecidos = numerosNoResumo.filter(n =>
  n > 2 && !numerosValidos.includes(n)
);

if (numerosDesconhecidos.length > 0) {
  // Fallback: usar template fixo com dados brutos
  return [{ json: { usarFallback: true, numerosInvalidos: numerosDesconhecidos } }];
}
```
