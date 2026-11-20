# Organizador de Pedidos (versão web)

Planejamento de produção em Streamlit. O algoritmo é o do notebook
`Organizador_Pedidos_Limite_10_Dias.ipynb`, copiado sem alterações.
Projeto acadêmico, com dados fictícios.

## Estrutura

| Arquivo | Função |
|---|---|
| `main.py` | Ponto de entrada (`streamlit run main.py`) |
| `interface.py` | Tela: cartões, tabelas, botões, confirmação. Sem regra de negócio |
| `servico.py` | Junta planilha + banco + algoritmo e entrega o estado pronto para a tela |
| `planejador.py` | Calendário e algoritmo (cópia literal do notebook) + `planejar_com_fixado` |
| `pedidos.py` | Classes e validação (cópia literal) + leitura do JSON e do CSV |
| `banco.py` | Persistência: Supabase (Postgres) em produção, SQLite só para uso local |
| `produtos.json` | Seus produtos. **Somente leitura**, nunca é modificado |
| `testes.py` | Testes do notebook + testes novos |
| `pedidos_exemplo.csv` | Pedidos fictícios para testar sem a planilha |
| `.streamlit/config.toml` | Tema escuro |
| `.streamlit/secrets.toml.example` | Modelo dos segredos (link da planilha e senha do banco) |

## Regras implementadas

- **Pedido iniciado** fica fixo na 1ª posição de PEDIDOS EM PRODUÇÃO, mesmo após
  atualizar a página ou reiniciar o app. Os demais são ordenados pelo
  algoritmo original, começando quando o pedido iniciado termina.
- **Só um pedido em produção por vez.** Isso é garantido pelo próprio banco
  (índice único), então vale mesmo com várias pessoas clicando juntas.
- A interface separa produção e histórico em duas abas.
- O cronômetro usa o horário real salvo ao iniciar; continua contando após
  atualizar ou reabrir a aplicação. Ao concluir, o tempo total fica no histórico.
- **Finalizar** move o pedido para PEDIDOS CONCLUÍDOS com os dados originais
  preservados (um instantâneo é gravado ao iniciar). Depois disso o algoritmo
  reorganiza os restantes livremente.
- **Identificador persistente** de cada pedido: o carimbo de data/hora do Google
  Forms (envios no mesmo segundo ganham sufixo `#2`; sem carimbo, usa `linha-N`).
- Iniciar e finalizar pedem confirmação.

### Decisões que tomei e que você pode mudar

1. **FINALIZAR só funciona para o pedido em produção** (a 1ª linha). Não dá para
   finalizar um pedido que nunca foi iniciado. Se quiser permitir, é uma
   mudança pequena.
2. **Se o término previsto do pedido iniciado já passou**, os demais são
   planejados a partir de *agora*, pois não dá para planejar no passado.
3. **Os pedidos iniciados ou concluídos saem da validação da planilha.** A regra
   original rejeita datas de entrega anteriores a hoje; sem essa exceção, um
   pedido iniciado cuja entrega vence "sumiria" da tela.

## 1. Rodar no VS Code (modo local, sem configurar nada)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run main.py
```

O arquivo `.streamlit/secrets.toml` desta cópia já está preenchido com o link
CSV publicado que foi fornecido para o projeto. O banco continua em SQLite
local até que o Supabase seja configurado. Para conferir a lógica:
`python testes.py`. Não compartilhe o link CSV se ele expuser dados reais de clientes.

## 2. Configurar o Supabase (banco compartilhado)

1. Crie uma conta em supabase.com e clique em **New project**. Anote a
   **Database Password** (ela só aparece na criação).
2. Com o projeto criado, clique em **Connect** no topo do painel.
3. Escolha a conexão **Session pooler**. O Streamlit Community Cloud usa IPv4,
   e a conexão "Direct" do Supabase costuma ser só IPv6. A tela do Supabase
   pode mudar de lugar, então confirme na documentação deles.
4. Copie a string `postgresql://postgres.xxxx:[YOUR-PASSWORD]@...pooler.supabase.com:5432/postgres`
   e troque `[YOUR-PASSWORD]` pela sua senha. Se a senha tiver `@ : / # ?`,
   codifique (`@` vira `%40`). Mais simples: troque a senha por uma só com
   letras e números (Project Settings > Database > Reset password).
5. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e cole
   a string em `db_url`.
6. Rode `streamlit run main.py`. **A tabela é criada sozinha** no primeiro
   acesso (com RLS ligada, para a API pública do Supabase não enxergar nada).
   Depois de iniciar um pedido, veja-o em **Table Editor > pedidos_estado**.

Atenção: no plano gratuito o Supabase pausa projetos sem atividade por cerca de
uma semana. Antes da apresentação, abra o painel e use **Restore** se estiver
pausado.

## 3. Conectar a planilha (CSV publicado)

1. Abra a planilha de respostas do Forms. **Arquivo > Compartilhar > Publicar na Web**.
2. Escolha a aba de respostas e o formato **Valores separados por vírgula (.csv)**.
3. Clique em **Publicar** e copie o link. Cole em `planilha_csv_url` no `secrets.toml`.

Se a conta institucional bloquear "Publicar na Web", me avise: a alternativa é
um upload manual do CSV na própria tela.

**Riscos:** quem tiver o link do CSV lê a planilha inteira (nome do cliente,
produto, quantidade, entrega). Por isso use só dados fictícios. A atualização
pode levar alguns minutos para chegar ao link, e o app guarda a leitura por 60 s
(o botão **Atualizar** ignora esse cache).

## 4. Publicar na internet (Streamlit Community Cloud)

1. Suba a pasta para um repositório do GitHub (o `.gitignore` já exclui
   `secrets.toml` e o banco local). **Nunca** envie senhas para o GitHub.
2. Em share.streamlit.io: **Create app**, escolha o repositório e `main.py`.
3. Em **Advanced settings > Secrets**, cole o conteúdo do seu `secrets.toml`.
4. Faça o deploy e compartilhe o link.

## Riscos de não ter login

Qualquer pessoa com o link pode iniciar e finalizar pedidos, e não há como
desfazer uma finalização pela tela. As credenciais ficam só no servidor
(`st.secrets`) e nunca chegam ao navegador. Para um trabalho acadêmico com dados
fictícios isso é aceitável. Para uso real, seria preciso autenticação.

## Limitações conhecidas

- O planejamento depende da hora atual. Duas pessoas que abrem a página com
  minutos de diferença podem ver horários previstos ligeiramente diferentes.
- A tela atualiza sozinha em até ~20 s quando outra pessoa inicia ou finaliza
  um pedido. Pedidos novos na planilha aparecem em até ~1 min (ou no botão Atualizar).
- Valem as premissas do notebook: uma máquina, sem feriados, sem interrupções.
