# Panorama de Segurança — Template e Implementação (Parte 3)

## 7. Geração do Material Visual (Template PPTX)

### 7.1 Estrutura do Template Atual

O template "Template - Panorama de segurança.pptx" é um slide único (180x180cm, formato quadrado) com os seguintes elementos dinâmicos:

| Shape Name | Conteúdo Exemplo | Campo Dinâmico |
|-----------|-----------------|----------------|
| `Google Shape;60;p13` | "// Itaim Bibi em foco, panorama de segurança" | `{{regiao_nome}}` |
| `Google Shape;64;p13` | "[2023 - hoje]" | `{{periodo_inicio}} - {{periodo_fim}}` |
| `Google Shape;54;p13` | "58 Suspeitos indiciados com o auxílio da Gabriel" | `{{total_indiciados}}` |
| `Google Shape;61;p13` | "129 Total de ocorrências criminais analisadas" | `{{total_ocorrencias}}` |
| `Google Shape;62;p13` | "240 Câmeras espalhadas pela nossa Área de Proteção" | `{{total_cameras}}` |
| `Google Shape;63;p13` | "// Roubo, o crime mais comum na região" | `{{crime_mais_comum}}` |
| `Google Shape;65;p13` | "51 Roubo (Lei nº 2.848/40 - Art. 157)" | `{{top_crime_1_count}} {{top_crime_1_nome}}` |
| `Google Shape;66;p13` | "32 Furto (Lei nº 2.848/40 - Art. 155)" | `{{top_crime_2_count}} {{top_crime_2_nome}}` |
| `Google Shape;67;p13` | "22 Estelionato ..." | `{{top_crime_3_count}} {{top_crime_3_nome}}` |
| `Google Shape;68;p13` | "11 Colisão entre Veículos ..." | `{{top_crime_4_count}} {{top_crime_4_nome}}` |
| `Google Shape;70;p13` | "11 Tentativa de crime ..." | `{{top_crime_5_count}} {{top_crime_5_nome}}` |

### 7.2 Estratégia de Geração

**Nó 13: Code Node (Python via N8N Execute Command ou Code node)**

O N8N possui suporte a Python no Code node. Usaremos `python-pptx` para:
1. Abrir o template PPTX
2. Substituir os textos dinâmicos mantendo formatação (font, size, color)
3. Salvar como novo PPTX
4. Converter para imagem/PDF via LibreOffice headless

```python
from pptx import Presentation
from pptx.util import Pt, Emu
import json
import subprocess
import os

# Dados recebidos do nó anterior
dados = json.loads('{{$json.dados_consolidados}}')

# Mapeamento de shapes para dados
shape_map = {
    'Google Shape;60;p13': {
        'paragraphs': [
            f"// {dados['regiao_nome']} em foco,",
            f"     panorama de segurança"
        ]
    },
    'Google Shape;64;p13': {
        'paragraphs': [f"[{dados['periodo_inicio']} - {dados['periodo_fim']}]"]
    },
    'Google Shape;54;p13': {
        'paragraphs': [
            str(dados['total_indiciados']),
            "Suspeitos indiciados",
            "com o auxílio da Gabriel"
        ]
    },
    'Google Shape;61;p13': {
        'paragraphs': [
            str(dados['total_ocorrencias']),
            "Total de ocorrências ",
            "criminais analisadas"
        ]
    },
    'Google Shape;62;p13': {
        'paragraphs': [
            str(dados['total_cameras']),
            "Câmeras espalhadas pela nossa Área de Proteção"
        ]
    },
    'Google Shape;63;p13': {
        'paragraphs': [
            f"// {dados['crime_mais_comum']},",
            f"     o crime mais comum na região"
        ]
    },
}

# Top 5 crimes
crime_shapes = [
    'Google Shape;65;p13',
    'Google Shape;66;p13',
    'Google Shape;67;p13',
    'Google Shape;68;p13',
    'Google Shape;70;p13',
]

prs = Presentation('/templates/panorama_template.pptx')
slide = prs.slides[0]

for shape in slide.shapes:
    if shape.name in shape_map:
        config = shape_map[shape.name]
        # Atualizar texto preservando formatação dos runs existentes
        for i, para in enumerate(shape.text_frame.paragraphs):
            if i < len(config['paragraphs']):
                # Preservar formatação do primeiro run e atualizar texto
                if para.runs:
                    # Se o parágrafo tem um número grande (KPI), atualizar só o primeiro run
                    para.runs[0].text = config['paragraphs'][i]
                    # Limpar runs adicionais se existirem
                    for run in para.runs[1:]:
                        run.text = ''

    if shape.name in crime_shapes:
        idx = crime_shapes.index(shape.name)
        if idx < len(dados['top_crimes']):
            crime_nome, crime_count = dados['top_crimes'][idx]
            # Extrair nome curto do crime (sem lei)
            nome_curto = crime_nome.split(' (')[0] if ' (' in crime_nome else crime_nome
            lei = f" ({crime_nome.split(' (')[1]}" if ' (' in crime_nome else ''
            # Atualizar runs: número | nome | lei
            para = shape.text_frame.paragraphs[0]
            if len(para.runs) >= 2:
                para.runs[0].text = str(crime_count)
                para.runs[1].text = f" {nome_curto}"
                if len(para.runs) >= 4:
                    para.runs[3].text = lei

output_pptx = f'/tmp/panorama_{dados["lead_id"]}.pptx'
prs.save(output_pptx)

# Converter para PDF/imagem via LibreOffice
output_dir = '/tmp/'
subprocess.run([
    'libreoffice', '--headless', '--convert-to', 'png',
    '--outdir', output_dir, output_pptx
], check=True)

print(f'/tmp/panorama_{dados["lead_id"]}.png')
```

### 7.3 Conversão e Upload

**Nó 15: Upload do Material**
- **Opção A (recomendada):** Upload para um bucket S3/GCS e gerar URL pública
- **Opção B:** Upload como anexo no HubSpot via Files API:
```
POST https://api.hubapi.com/files/v3/files
Content-Type: multipart/form-data
```
- **Opção C:** Upload para Google Drive e compartilhar link

A URL resultante é salva na propriedade `panorama_material_url` do Lead.

---

## 8. Atualização Final do Lead no HubSpot

### Nó 16: PATCH Lead com Todas as Propriedades

```
PATCH https://api.hubapi.com/crm/v3/objects/0-136/{{leadId}}
Headers: Authorization: Bearer {{hubspot_token}}
Body:
{
  "properties": {
    "panorama_camada_dados": "bairro",
    "panorama_resumo_temporal": "📊 RESUMO 7 DIAS...",
    "panorama_material_url": "https://storage.../panorama_12345.png",
    "panorama_data_geracao": "2026-04-06T14:30:00Z",
    "panorama_regiao_nome": "Itaim Bibi",
    "panorama_status": "concluido"
  }
}
```

### Nó 17: Notificação ao Pré-Vendedor (Opcional)
- **Via Slack/Email:** Enviar notificação com link do lead e resumo rápido
- **Via HubSpot Task:** Criar tarefa automática para o pré-vendedor

---

## 9. Guardrails de IA

### 9.1 Princípio Fundamental
> A IA é usada APENAS para formatação de texto (resumo). Todos os números e dados vêm diretamente do Metabase. A IA NUNCA gera dados, faz inferências ou cria estatísticas.

### 9.2 Onde a IA é Usada
| Nó | Uso da IA | Guardrail |
|----|-----------|-----------|
| Nó 14 (Resumo) | Formatar dados brutos em texto legível | System prompt restritivo + validação pós-geração |

### 9.3 Onde a IA NÃO é Usada
| Componente | Abordagem | Motivo |
|-----------|-----------|--------|
| Template visual | Substituição direta de valores via python-pptx | Números devem ser 100% fiéis aos dados |
| Seleção de camada | Lógica determinística (thresholds) | Decisão baseada em regra, não em interpretação |
| Consultas SQL | Templates fixos com parâmetros | Segurança e previsibilidade |
| Geocodificação | API externa (ViaCEP/Nominatim) | Dado objetivo, sem margem para interpretação |

### 9.4 Validação Pós-IA (Nó 14b)
1. Extrair todos os números do texto gerado
2. Comparar com os números de entrada
3. Se houver número no texto que não existe nos dados → rejeitar e usar fallback
4. Fallback = template fixo com marcadores preenchidos programaticamente (sem IA)

### 9.5 Fallback sem IA
```
📊 RESUMO 7 DIAS ({{data_inicio_7d}} - {{data_fim}}):
• {{total_7d}} ocorrências registradas
• Tipos: {{crimes_7d_lista}}
• {{desfechos_7d}} desfechos validados
{{#if prisoes_7d}}• {{prisoes_7d}} prisões em flagrante{{/if}}

📊 RESUMO 15 DIAS ({{data_inicio_15d}} - {{data_fim}}):
• {{total_15d}} ocorrências registradas
• Tipos: {{crimes_15d_lista}}
• {{desfechos_15d}} desfechos validados

📊 RESUMO 30 DIAS ({{data_inicio_30d}} - {{data_fim}}):
• {{total_30d}} ocorrências registradas
• Top crimes: {{crimes_30d_top3}}
• {{desfechos_30d}} desfechos validados
{{#if prisoes_30d}}• {{prisoes_30d}} prisões em flagrante{{/if}}
• Ruas mais afetadas: {{ruas_30d_top3}}
```

---

## 10. Tratamento de Erros

| Cenário | Ação |
|---------|------|
| CEP inválido ou não encontrado | `panorama_status = "erro"`, notificar pré-vendedor |
| Geocodificação falha | Tentar Google Geocoding como fallback; se falhar, usar apenas bairro do ViaCEP |
| Metabase offline/timeout | Retry 3x com backoff exponencial (2s, 4s, 8s) |
| Token Metabase expirado | Re-autenticar automaticamente |
| Nenhum dado em nenhuma camada | `panorama_status = "sem_dados"`, notificar pré-vendedor |
| IA gera dados inválidos | Usar template fallback sem IA |
| Geração de imagem falha (LibreOffice) | Salvar PPTX como fallback e notificar |
| Upload de arquivo falha | Retry 2x; se falhar, salvar URL local e notificar |

---

## 11. Fases de Implementação

### Fase 1: Fundação (Prioridade Alta)
- [ ] Criar grupo de propriedades "Panorama de Segurança" no HubSpot
- [ ] Criar as 6 propriedades no objeto Lead (0-136)
- [ ] Configurar webhook de formulário no HubSpot → N8N
- [ ] Implementar nós 1-5 (webhook, validação, geocodificação, auth Metabase)

### Fase 2: Dados e Camadas
- [ ] Implementar consultas SQL para cada camada (Nós 6-9)
- [ ] Implementar lógica de threshold e escalada de camadas
- [ ] Implementar consulta de desfechos e câmeras (Nós 10-11)
- [ ] Implementar consolidação de dados (Nó 12)
- [ ] Testar com CEPs de regiões com diferentes volumes de dados

### Fase 3: Geração de Material
- [ ] Configurar ambiente Python no N8N (python-pptx + LibreOffice)
- [ ] Implementar geração do template PPTX (Nó 13)
- [ ] Implementar upload e armazenamento (Nó 15)
- [ ] Testar geração visual com dados reais

### Fase 4: IA e Resumo
- [ ] Implementar chamada à Claude API (Nó 14)
- [ ] Implementar validação pós-IA (Nó 14b)
- [ ] Implementar fallback sem IA
- [ ] Testar qualidade do resumo com diferentes cenários

### Fase 5: Integração e Go-Live
- [ ] Implementar atualização do Lead no HubSpot (Nó 16)
- [ ] Implementar notificações (Nó 17)
- [ ] Teste end-to-end com 10 CEPs variados
- [ ] Monitoramento e ajuste fino de thresholds

---

## 12. Testes Sugeridos

### CEPs para Teste (regiões com volumes variados)

| CEP | Região | Volume Esperado | Camada Esperada |
|-----|--------|----------------|-----------------|
| 22070-002 | Copacabana, RJ | Alto | Rua |
| 22420-020 | Ipanema, RJ | Alto | Rua |
| 22440-030 | Leblon, RJ | Alto | Rua |
| 05423-010 | Pinheiros, SP | Médio-Alto | Rua ou Bairro |
| 04538-133 | Itaim Bibi, SP | Médio | Bairro |
| 22631-010 | Barra da Tijuca, RJ | Médio | Bairro |
| 20040-020 | Centro, RJ | Médio | Bairro |
| 22271-030 | Laranjeiras, RJ | Médio-Baixo | Bairro ou Vizinhança |
| 01310-100 | Centro, SP | Médio | Bairro |
| 30130-001 | Centro, BH | Baixo | Zona |

---

## 13. Dependências e Pré-Requisitos

| Item | Status | Responsável |
|------|--------|-------------|
| Template PPTX no repositório | ✅ Disponível | — |
| Credenciais Metabase no N8N | ✅ Configurado | — |
| Credenciais HubSpot no N8N | ✅ Configurado | — |
| API Key Claude (Anthropic) | ⬜ Verificar | Equipe |
| API Key Google Geocoding (opcional) | ⬜ Decidir | Equipe |
| Bucket S3/GCS para armazenar imagens | ⬜ Configurar | Equipe |
| LibreOffice instalado no servidor N8N | ⬜ Verificar | Equipe |
| Python + python-pptx no servidor N8N | ⬜ Verificar | Equipe |
| Formulário HubSpot com campos CEP + Número | ⬜ Verificar/Criar | Equipe |
| Webhook HubSpot configurado | ⬜ Criar | Automação (N8N) |

---

## 14. Decisões em Aberto

1. **Geocodificação:** Nominatim (gratuito, menos preciso) vs Google (pago, mais preciso)?
   - **Recomendação:** Começar com Nominatim. Se a precisão não for suficiente, migrar para Google.

2. **Armazenamento de imagens:** S3, GCS, Google Drive ou HubSpot Files API?
   - **Recomendação:** HubSpot Files API (mantém tudo no ecossistema, sem custo adicional).

3. **Notificação ao pré-vendedor:** Slack, email ou apenas tarefa no HubSpot?
   - **Recomendação:** Tarefa no HubSpot (pré-vendedor já trabalha no CRM).

4. **Top crimes:** O template mostra 5. Se a região tiver menos de 5 tipos de crime, como tratar?
   - **Recomendação:** Mostrar quantos houver. Se < 5, ocultar as linhas vazias no template.
