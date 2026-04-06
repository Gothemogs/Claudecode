# Panorama de Segurança — Plano de Execução

## 1. Visão Geral do Projeto

### Objetivo
Automatizar a geração de materiais personalizados de proposta de valor para leads inbound da Gabriel, utilizando dados reais de ocorrências criminais, desfechos (indiciamentos/prisões) e câmeras instaladas na região do lead.

### Resultado Esperado
Quando um lead preencher o formulário (CEP + número de endereço), o sistema automaticamente:
1. Identifica a localização geográfica do lead
2. Consulta o Metabase para obter dados da região
3. Seleciona a camada geográfica com dados representativos
4. Gera um material visual (PDF/imagem) baseado no template "Panorama de Segurança"
5. Gera um resumo textual temporal (7/15/30 dias) para o pré-vendedor
6. Popula 3 propriedades no objeto Lead (0-136) do HubSpot

### Stack Tecnológico
| Componente | Ferramenta | Função |
|-----------|-----------|--------|
| CRM | HubSpot | Recebe formulário, armazena propriedades no Lead (0-136) |
| Automação | N8N | Orquestra todo o fluxo via webhooks e HTTP requests |
| Dados | Metabase (Redshift-Prod) | Fonte de dados de ocorrências, desfechos e câmeras |
| Geocodificação | ViaCEP + Nominatim/OpenStreetMap | Converte CEP + número → lat/lon (gratuito, sem limite de API) |
| IA (resumo) | Claude API | Gera resumo textual para speech do pré-vendedor |
| Geração visual | python-pptx (via N8N Code node) | Popula o template PPTX com dados e exporta como imagem/PDF |

---

## 2. Fontes de Dados no Metabase

### 2.1 Ocorrências (source-table: 1276)
- **Banco:** Redshift-Prod (database: 10)
- **Card original:** 249 (collection 153, dashboard 29)
- **Filtros base:** EfetividadeAnalise = "Efetiva" AND (DataHoraCriacao < "2025-07-01" OR TipoRegistro = "Ofício" OR TipoRegistro = "Procedimento")
- **Campos para consulta:** IDTicket, TipoCrime, Bairro, Estado, Cidade, Endereco, Zona, Latitude, Longitude, DataOcorrencia, Horario, PessoasIndiciadas, TipoSolicitante, TipoRegistro

### 2.2 Desfechos Solucionados
- **Banco:** Redshift-Prod (database: 10)
- **Campos para consulta:** IDDesfecho, DataDoDesfecho, Bairro, Cidade, UF, Zona, Logradouro, Latitude, Longitude, HouvePrisaoEmFlagrante, QtdIndiciadosDosTickets, TipoLocal, BaseParaDesfecho

### 2.3 Câmeras Externas (source-table: 1049)
- **Banco:** Redshift-Prod (database: 10)
- **Tabela:** EventoItemAssinatura
- **Card original:** 648
- **Campos para consulta:** VariacaoQuantidade, Situacao, Bairro, Cidade, UF, Zona, RotaComercial, IDLocal, NomeProduto
- **Filtro:** Situacao = "Ativo" para contagem atual de câmeras
- **Lógica:** Soma acumulada de VariacaoQuantidade por região para obter total de câmeras ativas

### 2.4 Acesso via N8N
Todas as consultas serão feitas via **HTTP Request** ao Metabase API:
```
POST https://dados.gabriel.com.br/api/dataset
Headers: X-Metabase-Session: {session_token}
Body: { "database": 10, "type": "native", "native": { "query": "SELECT ...", "template-tags": {} } }
```

**Autenticação Metabase:**
```
POST https://dados.gabriel.com.br/api/session
Body: { "username": "...", "password": "..." }
→ Retorna session token
```

---

## 3. Camadas Geográficas e Thresholds

### 3.1 Definição das Camadas (da mais granular para a mais ampla)

| # | Camada | Definição | Como Identificar |
|---|--------|-----------|-----------------|
| 1 | **Rua** | Mesma rua (logradouro) do lead | Match por nome de rua normalizado |
| 2 | **Ruas Próximas** | Ruas dentro de 500m do endereço do lead | Cálculo Haversine com lat/lon |
| 3 | **Bairro** | Mesmo bairro do lead | Match por nome de bairro |
| 4 | **Vizinhança** | Bairros com centróide dentro de 3km do bairro do lead | Cálculo Haversine entre centróides |
| 5 | **Zona** | Mesma zona (Sul, Norte, Oeste, Leste, Centro) | Match por campo Zona |

### 3.2 Thresholds Mínimos (fundamentação estatística)

Análise realizada sobre a base completa de 10.338 ocorrências e 4.666 desfechos:

**Dados observados:**
- Ruas: mediana = 2 ocorrências, P75 = 5, P90 = 10 (2.212 ruas únicas)
- Bairros: mediana = 9 ocorrências, P75 = 29 (210 bairros únicos)
- Zonas: mínimo = 1, máximo = 4.502

**Critério:** O material deve transmitir volume e relevância. Números muito baixos enfraquecem a proposta de valor. O threshold combina:
- Mínimo de ocorrências (volume de inteligência)
- Mínimo de desfechos (prova de efetividade)

| Camada | Mín. Ocorrências | Mín. Desfechos | Justificativa |
|--------|------------------|----------------|---------------|
| Rua | 5 | 2 | P75 das ruas = 5. Garante que não mostramos dados anêmicos |
| Ruas Próximas | 10 | 3 | Agregação de ~3-8 ruas. Dobro do threshold de rua |
| Bairro | 15 | 5 | Mediana dos bairros = 9, garantimos acima da mediana |
| Vizinhança | 25 | 8 | Agregação de 2-5 bairros. Números robustos |
| Zona | 0 (sem mínimo) | 0 (sem mínimo) | Fallback final — sempre tem dado |

**Lógica de escalada:** Se a camada atual não atinge o threshold → sobe para a próxima camada. Se nenhuma camada atinge (improvável), usa Zona como fallback.

### 3.3 Normalização de Endereços

Problema identificado nos dados: mesma rua com grafias diferentes.
Exemplos: "Avenida Atlântica" vs "Av. Atlântica" | "R. Visc. de Pirajá" vs "Rua Visconde de Pirajá"

**Solução:** Função de normalização no N8N (Code node):
1. Expandir abreviações: R. → Rua, Av. → Avenida, Al. → Alameda, Pç. → Praça, Trav. → Travessa
2. Remover acentos e converter para lowercase
3. Remover números (complementos de endereço)
4. Trim e remover espaços duplos

---

## 4. Propriedades HubSpot a Criar

### Objeto: Lead (0-136)

#### 4.1 Propriedade: `panorama_camada_dados`
- **Label:** Panorama - Camada de Dados
- **Tipo:** Enumeração (dropdown)
- **Opções:**
  - `rua` — Rua
  - `ruas_proximas` — Ruas Próximas (500m)
  - `bairro` — Bairro
  - `vizinhanca` — Vizinhança (3km)
  - `zona` — Zona
- **Grupo:** Panorama de Segurança
- **Descrição:** Camada geográfica selecionada automaticamente com base na disponibilidade de dados representativos na região do lead.

#### 4.2 Propriedade: `panorama_resumo_temporal`
- **Label:** Panorama - Resumo Temporal
- **Tipo:** Texto multilinha (textarea)
- **Grupo:** Panorama de Segurança
- **Descrição:** Resumo textual gerado por IA com dados de 7, 15 e 30 dias da região do lead. Usado pelo pré-vendedor no speech de abordagem.
- **Formato do conteúdo:**
```
📊 RESUMO 7 DIAS (01/04 - 06/04):
• 3 ocorrências registradas (2 Roubos, 1 Furto)
• 1 suspeito indiciado com auxílio Gabriel
• Rua mais afetada: Rua Dias Ferreira

📊 RESUMO 15 DIAS (22/03 - 06/04):
• 8 ocorrências registradas (4 Roubos, 2 Furtos, 1 Estelionato, 1 Colisão)
• 3 suspeitos indiciados com auxílio Gabriel
• Horário de maior incidência: 18h-21h

📊 RESUMO 30 DIAS (07/03 - 06/04):
• 15 ocorrências registradas
• Top crimes: Roubo (7), Furto (4), Estelionato (2)
• 5 suspeitos indiciados, 1 prisão em flagrante
• Gabriel atuou em 60% dos casos com ofício à polícia
```

#### 4.3 Propriedade: `panorama_material_url`
- **Label:** Panorama - Material Personalizado
- **Tipo:** URL (ou Arquivo, se disponível)
- **Grupo:** Panorama de Segurança
- **Descrição:** URL do material visual (PDF/imagem) gerado automaticamente com os dados da região do lead, baseado no template "Panorama de Segurança".

#### 4.4 Propriedade: `panorama_data_geracao`
- **Label:** Panorama - Data de Geração
- **Tipo:** Date (datetime)
- **Grupo:** Panorama de Segurança
- **Descrição:** Data/hora em que o material foi gerado. Útil para controle de atualidade dos dados.

#### 4.5 Propriedade: `panorama_regiao_nome`
- **Label:** Panorama - Nome da Região
- **Tipo:** Texto (single line)
- **Grupo:** Panorama de Segurança
- **Descrição:** Nome da região usada no material (ex: "Itaim Bibi", "Zona Sul - RJ"). Facilita busca e segmentação.

#### 4.6 Propriedade: `panorama_status`
- **Label:** Panorama - Status de Geração
- **Tipo:** Enumeração (dropdown)
- **Opções:**
  - `pendente` — Pendente
  - `processando` — Processando
  - `concluido` — Concluído
  - `erro` — Erro na Geração
  - `sem_dados` — Sem Dados na Região
- **Grupo:** Panorama de Segurança
- **Descrição:** Status do processamento do material. Permite monitorar falhas e re-execuções.
