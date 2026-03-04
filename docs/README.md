# Pasta de Documentação do Catálogo

Esta pasta contém os documentos de referência e os dados estruturados usados para
popular o catálogo de selos.

## Convenção de pastas

Cada **subdiretoria** representa um **país** e o seu nome é usado como nome do país
no catálogo. Ao executar o comando de importação, qualquer diretoria aqui presente
é automaticamente criada/atualizada como um `Pais` no sistema.

```
docs/
├── Espanha/
│   ├── pais.json                          ← metadados do país (código ISO, etc.)
│   ├── selos.csv                          ← dados dos selos para importar
│   └── Edifil 2012 España y ....pdf       ← documentos de referência (ignorados)
├── Portugal/
│   ├── pais.json
│   ├── selos.csv
│   └── CTT Catalogo 2023.pdf
└── ...
```

## Ficheiro `pais.json`

Metadados do país. Se não existir, o país é criado apenas com o nome da pasta.

```json
{
  "codigo_iso": "ES",
  "descricao": "Catálogo Edifil — Espanha e Dependências Postais."
}
```

| Campo        | Obrigatório | Descrição                              |
|--------------|-------------|----------------------------------------|
| `codigo_iso` | Sim         | Código ISO 3166-1 (2 ou 3 letras)      |
| `descricao`  | Não         | Texto descritivo do país no catálogo   |

## Ficheiro `selos.csv`

Dados dos selos para importar. Codificação: **UTF-8**. Separador: **vírgula (`,`)**.

### Colunas

| Coluna              | Obrigatório | Exemplo                                  |
|---------------------|-------------|------------------------------------------|
| `numero_catalogo`   | Sim         | `ES-2012-001` ou `Edifil 1234`           |
| `titulo`            | Sim         | `Fauna Ibérica — Lince`                  |
| `ano`               | Sim         | `2012`                                   |
| `denominacao`       | Sim         | `0.65`                                   |
| `moeda`             | Sim         | `EUR`                                    |
| `descricao_tematica`| Sim         | `Lince ibérico, espécie em recuperação.` |
| `descricao_tecnica` | Não         | `Offset 4 cores. 40×30mm. Dent. 13½.`   |
| `dentado`           | Não         | `13½`                                    |
| `tiragem`           | Não         | `1000000`                                |
| `temas`             | Não         | `Fauna` ou `Fauna;Flora` (`;` separador) |

### Exemplo

```csv
numero_catalogo,titulo,ano,denominacao,moeda,descricao_tematica,descricao_tecnica,dentado,tiragem,temas
ES-2012-001,Fauna Ibérica — Lince,2012,0.65,EUR,O lince ibérico em habitat natural.,Offset 4 cores. Formato 40×30mm.,13½,1000000,Fauna
ES-2012-002,Arquitectura Modernista,2012,0.36,EUR,Edifício Batlló de Gaudí em Barcelona.,Calcografia. Formato 28×40mm.,13¾,800000,Arte;Arquitectura
```

## Comando de importação

```bash
# Importar todos os países de docs/
docker compose exec web python manage.py importar_catalogo

# Importar apenas um país
docker compose exec web python manage.py importar_catalogo --pais Espanha

# Apenas criar países, sem importar selos
docker compose exec web python manage.py importar_catalogo --apenas-paises

# Forçar atualização de registos já existentes
docker compose exec web python manage.py importar_catalogo --forcar
```

## Notas

- Os ficheiros PDF, JPG, e outros documentos nas pastas são ignorados pelo importador — servem apenas como referência humana.
- O campo `numero_catalogo` é único por país, portanto reimportar o mesmo ficheiro não cria duplicados.
- Temas são criados automaticamente se não existirem.
- **Campos com vírgulas** devem ser envolvidos em aspas duplas no CSV: `"Miguel de Cervantes (1547–1616), autor de Dom Quixote."`
