# Contexto dos Dados — Sessão de Análise

## Visão Geral

Três arquivos CSV extraídos de um sistema de gestão de ocorrências (HubSpot CRM) da empresa **Gabriel** — uma empresa de segurança/monitoramento urbano que utiliza câmeras ("Camaleões") instaladas em imóveis de clientes para auxiliar na identificação e resolução de crimes.

---

## 1. Dados Ocorrências.csv (~12 MB)

- **Linhas:** 10.338 registros
- **Colunas:** 56
- **Descrição:** Tickets de ocorrências criminais registradas no pipeline de Inteligência. Cada linha é um ticket com dados da ocorrência (tipo de crime, localização, data, descrição), dados operacionais (pipeline, prioridade, responsável, tempo de resposta) e dados de efetividade (links de vídeo, pessoas indiciadas).

### Colunas-chave:
| Coluna | Descrição |
|--------|-----------|
| IDTicket | Identificador único do ticket |
| Categoria | "Relato de Ocorrência" |
| Pipeline / EtapaPipeline | Fluxo de trabalho (Inteligência → Concluído / Em Andamento / Andamento RelGov) |
| Prioridade | HIGH (7.604), LOW (2.254), URGENT (48), MEDIUM (35) |
| DataHoraCriacao / DataOcorrencia | Quando o ticket foi criado vs. quando o crime ocorreu |
| TipoCrime | 51 tipos — top: Roubo (3.300), Furto (2.780), Colisão (771), Tentativa (571), Estelionato (508) |
| Estado/Cidade/Bairro/Zona | Localização — RJ (7.257), SP (3.045), MG (14) |
| TipoRegistro | Nenhum (5.196), Ofício (2.928), Procedimento (2.214) |
| TipoSolicitante | Cliente (4.770), Polícia (3.187), Não Cliente (1.954), Funcionário (377) |
| EfetividadeAnalise | 100% Efetiva |
| PessoasIndiciadas | Quantidade de indiciados por ticket |
| RotaComercial | Agrupamento comercial por região/bairro |
| Horario/Intervalo | Hora do crime e faixa horária |
| LinkVideo / LinkVideoSemMarcacoes | Links para evidências em vídeo |

### Bairros mais frequentes:
Copacabana (931), Ipanema (856), Leblon (774), Tijuca (693), Pinheiros (589), Barra da Tijuca (459), Botafogo (393)

### Zonas:
- RJ Zona Sul: 4.502
- RJ Zona Norte: 1.523
- SP Zona Oeste: 1.361
- SP Zona Sul: 1.236
- RJ Zona Oeste: 926

---

## 2. Dados Desfechos Solucionados.csv (~3.2 MB)

- **Linhas:** 4.666 registros
- **Colunas:** 57
- **Descrição:** Desfechos validados (indiciamentos) vinculados a locais/assinaturas de clientes. Cada linha representa um desfecho positivo (pessoa indiciada) associado a um local monitorado.

### Colunas-chave:
| Coluna | Descrição |
|--------|-----------|
| IDDesfecho | Identificador único do desfecho |
| TipoDeDesfecho | 100% "Indiciado" |
| FoiDesfechoValido | 100% "Sim" |
| DataDoDesfecho | Data do indiciamento |
| EstadoDesfecho | RJ (3.969), SP (695), MG (2) |
| HouvePrisaoEmFlagrante | Sim (504), Não (1.079) |
| PodeDivulgar | Sim (1.411), Não (193) |
| BaseParaDesfecho | Ofício + Link da Matéria (2.739), Somente Ofício (1.841), Ofício + Print (86) |
| FonteDoDesfecho | Mídia (288), Polícia (250) |
| IDAssinatura / TituloAssinatura | Contrato/assinatura do cliente |
| IDLocal / NomeLocal / TipoLocal | Local monitorado — Condomínio Residencial (3.390), Comércio (481), Casa (341) |
| Situacao | Ativo (3.798), Finalizado (837) |
| TipoTermo | Adesão (2.731), Aditivo (1.902) |
| QtdTicketsAssociados / QtdTicketsEfetivosAssociados | Métricas de associação com tickets |
| QtdIndiciadosDosTickets | Total de indiciados nos tickets vinculados |
| QtdPrisoesValidasEmTicketsAssociados | Prisões confirmadas |
| RotaComercial / AsaComercial | Agrupamento comercial |

---

## 3. Dados Desfecho.csv (~366 KB)

- **Linhas:** 800 registros
- **Colunas:** 11
- **Descrição:** Desfechos com informações de retorno ao cliente — contém dados de comunicação sobre ocorrências solucionadas, incluindo resumo, legenda e arte do desfecho para envio ao cliente.

### Colunas:
| Coluna | Descrição |
|--------|-----------|
| Data de criação | Data de criação do registro (negócio/deal) |
| Date entered "Retorno Concluído" | Data em que o retorno foi concluído |
| Estado / Cidade / Bairro / Logradouro | Localização |
| (Desfecho) Resumo da Ocorrência | Texto resumo do caso solucionado |
| [CS] Legenda do Desfecho | Texto de comunicação ao cliente (ex: "Com o apoio dos Camaleões...") |
| [CS] Arte de Desfecho | Nome do arquivo de imagem/relatório visual |
| Negócio ID | ID do negócio/deal no CRM |
| Local ID | ID do local monitorado |

### Distribuição:
- RJ: 604, SP: 188, Niterói: 16
- 157 datas de criação únicas, 75 datas de retorno únicas
- Top bairros: Copacabana (120), Lagoa (66), Jardim Botânico (65)
- Muitos registros com "(Nenhum valor)" em campos de desfecho — indicando ocorrências ainda sem retorno finalizado

---

## Relações entre os Arquivos

```
Dados Ocorrências (tickets)
    ↕ IDTicket ↔ QtdTicketsAssociados
Dados Desfechos Solucionados (desfechos validados por local)
    ↕ IDLocal / Negócio ID
Dados Desfecho (comunicação de retorno ao cliente)
```

- **Ocorrências → Desfechos Solucionados:** Cada desfecho pode ter múltiplos tickets associados (QtdTicketsAssociados)
- **Desfechos Solucionados → Desfecho:** Vinculados por Local ID e possivelmente Negócio ID
- A granularidade é diferente: Ocorrências é por ticket, Desfechos Solucionados é por desfecho+local, Desfecho é por negócio+local

---

## Contexto do Negócio

A **Gabriel** é uma empresa de segurança urbana que:
1. Instala câmeras ("Camaleões") em imóveis de clientes (condomínios, comércios, casas)
2. Monitora e analisa ocorrências criminais nas áreas de cobertura
3. Colabora com a polícia fornecendo evidências em vídeo (ofícios)
4. Comunica aos clientes quando ocorrências são solucionadas (desfechos)
5. Opera principalmente no RJ (Zona Sul forte) e SP
6. Usa HubSpot como CRM para gestão de tickets e pipeline de inteligência
