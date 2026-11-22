"""
interface.py - Camada visual (Streamlit). Não contém regra de negócio:
apenas exibe o estado calculado por servico.py e dispara iniciar/finalizar.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
from pathlib import Path

import streamlit as st

import pedidos
import servico
from banco import Banco, ErroDeNegocio

PASTA = Path(__file__).parent
CSV_DEMO = PASTA / "pedidos_exemplo.csv"
BANCO_LOCAL = f"sqlite:///{PASTA / 'dados_locais.db'}"

ALTURA_PRODUCAO = 460     # px: tabela principal (rolagem própria)
ALTURA_CONCLUIDOS = 460   # px: tabela de histórico na aba própria

CSS = """
<style>
:root{
  --fundo:#0e1420; --painel:#161e2e; --painel2:#1c2639; --borda:#27324a;
  --texto:#e8edf6; --suave:#93a0b8; --azul:#3b82f6;
  --verde:#22c55e; --ambar:#f59e0b; --vermelho:#ef4444;
}
.stApp{background:var(--fundo); color:var(--texto);}
#MainMenu, footer{visibility:hidden;}
[data-testid="stHeader"]{background:transparent;}
.block-container{max-width:1500px; padding-top:1.6rem; padding-bottom:3rem;}

.topo{display:flex; align-items:baseline; gap:.9rem; flex-wrap:wrap;}
.topo h1{font-size:1.75rem; font-weight:700; letter-spacing:.02em; margin:0; padding:0;}
.topo span{color:var(--suave); font-size:.9rem;}

.cartoes{display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
         gap:.8rem; margin:1rem 0 1.2rem 0;}
.cartao{background:var(--painel); border:1px solid var(--borda);
        border-radius:12px; padding:.85rem 1rem; border-left:4px solid var(--azul);}
.cartao .rotulo{color:var(--suave); font-size:.74rem; letter-spacing:.07em;
                text-transform:uppercase;}
.cartao .valor{font-size:1.9rem; font-weight:700; line-height:1.15; margin-top:.15rem;}
.cartao .valor.texto{font-size:1.15rem; padding-top:.45rem; white-space:nowrap;
                     overflow:hidden; text-overflow:ellipsis;}
.cartao.verde{border-left-color:var(--verde);}
.cartao.ambar{border-left-color:var(--ambar);}
.cartao.vermelho{border-left-color:var(--vermelho);}

.titulo-painel{font-size:1.05rem; font-weight:700; letter-spacing:.09em;
               margin:.2rem 0 .1rem 0;}
.sub-painel{color:var(--suave); font-size:.82rem; margin-bottom:.5rem;}

[data-testid="stVerticalBlockBorderWrapper"]{background:var(--painel);
        border-color:var(--borda)!important; border-radius:14px;}

.detalhe{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
         gap:.4rem .9rem; background:var(--painel2); border:1px solid var(--borda);
         border-radius:10px; padding:.7rem .9rem; margin-top:.6rem; font-size:.86rem;}
.detalhe b{display:block; color:var(--suave); font-weight:500; font-size:.7rem;
           letter-spacing:.06em; text-transform:uppercase;}

.aviso{border-radius:10px; padding:.65rem .9rem; margin:.3rem 0 .9rem 0;
       font-size:.88rem; border:1px solid var(--borda); background:var(--painel);}
.aviso.ok{border-left:4px solid var(--verde);}
.aviso.alerta{border-left:4px solid var(--ambar);}

div.stButton > button{border-radius:9px; font-weight:600; letter-spacing:.03em;
                      padding:.55rem 1.1rem;}
.st-key-btn_finalizar button{border:1px solid var(--verde)!important;
                             color:var(--verde)!important; background:transparent!important;}
.st-key-btn_finalizar button:disabled{opacity:.4;}
.st-key-btn_finalizar button:hover:not(:disabled){background:rgba(34,197,94,.12)!important;}

@media (max-width: 700px){
  .topo h1{font-size:1.4rem;}
  .cartao .valor{font-size:1.5rem;}
}
</style>
"""


# ----------------------------------------------------------------- recursos
def _segredo(*caminho):
    """Lê st.secrets (ou None, se não existir/configurado)."""
    try:
        valor = st.secrets
        for parte in caminho:
            valor = valor[parte]
        return str(valor) or None
    except Exception:
        return None


@st.cache_resource(show_spinner="Conectando ao banco...")
def _obter_banco(url):
    return Banco(url)


@st.cache_data(ttl=60, show_spinner=False)
def _carregar_planilha(origem):
    return pedidos.ler_planilha(origem)


def _tabela(df, **kwargs):
    """st.dataframe ocupando toda a largura, em qualquer versão do Streamlit."""
    try:
        return st.dataframe(df, width="stretch", **kwargs)
    except TypeError:
        return st.dataframe(df, use_container_width=True, **kwargs)


# ----------------------------------------------------------------- componentes
def _cartoes(k):
    def cartao(rotulo, valor, cor="", texto=False):
        classe = "valor texto" if texto else "valor"
        return (f'<div class="cartao {cor}"><div class="rotulo">{escape(rotulo)}</div>'
                f'<div class="{classe}">{escape(str(valor))}</div></div>')

    st.markdown(
        '<div class="cartoes">'
        + cartao("Pedidos em produção", k["em_producao"])
        + cartao("Pedidos concluídos", k["concluidos"], "verde")
        + cartao("Pedidos atrasados", k["atrasados"], "ambar")
        + cartao(f"Acima do limite ({servico.LIMITE_ATRASO_DIAS} dias)",
                 k["acima_limite"], "vermelho")
        + cartao("Em andamento agora", k["em_andamento"] or "—", "", texto=True)
        + "</div>", unsafe_allow_html=True)


def _estilo_producao(df):
    def linha(r):
        if str(r["Status"]).startswith("●"):
            cor = "#17325a"      # azul: em produção
        elif r["Dias além do limite"] > 0:
            cor = "#4a1f27"      # vermelho: acima do limite
        elif r["Dias de atraso"] > 0:
            cor = "#47391a"      # âmbar: atrasado, dentro do limite
        else:
            cor = ""

        return [
            f"background-color: {cor}; color: #e8edf6;" if cor
            else "color: #e8edf6;"
        ] * len(r)

    return df.style.apply(linha, axis=1)


def _estilo_concluidos(df):
    return df.style.apply(
        lambda r: [
            "background-color: #14352a; color: #e8edf6;"
        ] * len(r),
        axis=1
    )


def _detalhes(ped, linha_df):
    campos = [
        ("Cliente", linha_df["Cliente"]), ("Produto", linha_df["Produto"]),
        ("Quantidade", linha_df["Quantidade"]),
        ("Tempo total", f'{linha_df["Tempo total (min)"]} min'),
        ("Entrega", linha_df["Data de entrega"]),
        ("Início previsto", linha_df["Início da produção"]),
        ("Conclusão prevista", linha_df["Conclusão"]),
        ("Situação", linha_df["Situação"]),
        ("Registro (carimbo)", ped.chave),
    ]
    html = "".join(f"<div><b>{escape(r)}</b>{escape(str(v))}</div>" for r, v in campos)
    st.markdown(f'<div class="detalhe">{html}</div>', unsafe_allow_html=True)


def _duracao_texto(inicio):
    """Tempo decorrido desde o horário persistido de início."""
    inicio_dt = datetime.fromisoformat(inicio)
    agora_dt = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    segundos = max(0, int((agora_dt - inicio_dt).total_seconds()))
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)
    prefixo = f"{dias}d " if dias else ""
    return f"{prefixo}{horas:02d}:{minutos:02d}:{segundos:02d}"


@st.fragment(run_every="1s")
def _temporizador(iniciado_em):
    """Atualiza somente o relógio, sem reiniciar o horário salvo no banco."""
    st.metric("TEMPO DE PRODUÇÃO", _duracao_texto(iniciado_em))


@st.dialog("Confirmar ação")
def _confirmar(acao, ped_info, banco, agora):
    verbo = "INICIAR a produção" if acao == "iniciar" else "FINALIZAR"
    st.write(f"Deseja **{verbo}** do pedido de **{ped_info['cliente']}** "
             f"({ped_info['produto']}, {ped_info['quantidade']} un.)?")
    if acao == "iniciar":
        st.caption("O pedido ficará fixo na 1ª posição até ser finalizado.")
    else:
        st.caption("O pedido será movido para PEDIDOS CONCLUÍDOS.")
    c1, c2 = st.columns(2)
    if c1.button("Confirmar", type="primary", key="dlg_ok"):
        try:
            # Registra o horário real da ação (com segundos) no banco.
            agora_real = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
            if acao == "iniciar":
                banco.iniciar(ped_info, agora_real)
                st.session_state["msg"] = ("ok", "Produção iniciada.")
            else:
                banco.finalizar(ped_info["chave"], agora_real)
                st.session_state["msg"] = ("ok", "Pedido finalizado e movido para concluídos.")
        except ErroDeNegocio as erro:
            st.session_state["msg"] = ("erro", str(erro))
        st.session_state["versao"] = st.session_state.get("versao", 0) + 1
        st.rerun()
    if c2.button("Cancelar", key="dlg_cancel"):
        st.rerun()


@st.fragment(run_every="20s")
def _vigia(banco):
    """Atualiza a página sozinha quando OUTRA pessoa inicia/finaliza algo."""
    atual = banco.assinatura()
    ref = st.session_state.get("_assinatura")
    if ref is not None and atual != ref:
        st.session_state["_assinatura"] = atual
        st.session_state["versao"] = st.session_state.get("versao", 0) + 1
        st.rerun(scope="app")


# ----------------------------------------------------------------- página
def render():
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("versao", 0)

    # ---- origem dos dados: segredos (produção) ou modo local (demonstração) ----
    url_banco = _segredo("supabase", "db_url") or os.environ.get("DATABASE_URL")
    url_csv = _segredo("planilha_csv_url") or os.environ.get("PLANILHA_CSV_URL")
    modo_local_banco = not url_banco
    modo_local_csv = not url_csv

    try:
        banco = _obter_banco(url_banco or BANCO_LOCAL)
    except Exception as erro:
        st.error("Não foi possível conectar ao banco de dados. Confira a "
                 "`db_url` em `.streamlit/secrets.toml` (ou nos Secrets do app).")
        st.caption(f"Detalhe técnico: {type(erro).__name__}")
        st.stop()

    # ---- cabeçalho ----
    col_t, col_b = st.columns([6, 1])
    with col_t:
        st.markdown('<div class="topo"><h1>Organizador de Pedidos</h1>'
                    '<span>Planejamento e controle de produção</span></div>',
                    unsafe_allow_html=True)
    with col_b:
        if st.button("↻ Atualizar", key="btn_atualizar"):
            _carregar_planilha.clear()
            st.session_state["versao"] += 1
            st.rerun()

    # ---- mensagens ----
    tipo, texto = st.session_state.pop("msg", (None, None))
    if tipo == "ok":
        st.success(texto)
    elif tipo == "erro":
        st.error(texto)
    if modo_local_banco:
        st.warning("Modo local: usando SQLite neste computador. Para compartilhar "
                   "os dados pela internet, configure o Supabase (veja o README).")
    if modo_local_csv:
        st.info("Modo demonstração: lendo `pedidos_exemplo.csv`. Configure "
                "`planilha_csv_url` para ler a planilha do Google Forms.")

    # ---- carga e planejamento ----
    try:
        df_pedidos = _carregar_planilha(url_csv or str(CSV_DEMO))
    except KeyError as erro:
        st.error(f"Planilha em formato inesperado. {erro.args[0]}")
        st.stop()
    except Exception as erro:
        st.error("Não foi possível ler a planilha de pedidos. Confira se o link CSV "
                 "publicado está correto e acessível.")
        st.caption(f"Detalhe técnico: {type(erro).__name__}")
        st.stop()

    st.session_state["_assinatura"] = banco.assinatura()
    agora = servico.agora_sp()
    estado = servico.montar_estado(df_pedidos, banco, agora)
    k = estado["kpis"]
    resumo = estado["resumo"]

    _cartoes(k)

    if resumo:
        lim = resumo["limite_dias"]
        if resumo["regra_respeitada"]:
            st.markdown(f'<div class="aviso ok">Nenhum pedido ultrapassa {lim} dias de '
                        f'atraso na sequência atual.</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="aviso alerta"><b>Atenção:</b> não é possível respeitar o '
                f'limite de {lim} dias para todos os pedidos. Pedidos acima do limite: '
                f'<b>{resumo["acima_limite"]}</b> (maior atraso: {resumo["maior_atraso"]} '
                f'dias corridos).</div>', unsafe_allow_html=True)

    # ---- abas principais ----
    producao, chaves = estado["producao"], estado["chaves"]
    versao = st.session_state["versao"]
    aba_producao, aba_concluidos = st.tabs([
        f"📋 Pedidos em produção ({len(producao)})",
        f"✅ Pedidos concluídos ({len(estado['concluidos'])})",
    ])

    with aba_producao:
        with st.container(border=True):
            st.markdown('<div class="titulo-painel">PEDIDOS EM PRODUÇÃO</div>'
                        '<div class="sub-painel">Sequência calculada pelo algoritmo. Clique '
                        'numa linha para selecionar. O pedido em produção fica sempre na '
                        '1ª posição.</div>', unsafe_allow_html=True)

            em_prod = estado["em_producao"]
            if em_prod:
                _temporizador(em_prod["iniciado_em"])
                st.caption("O cronômetro usa o horário de início salvo no banco e continua "
                           "mesmo após atualizar ou reabrir a página.")

            area_botoes = st.container()
            if producao.empty:
                st.info("Nenhum pedido aguardando produção.")
                evento = None
            else:
                evento = _tabela(
                    _estilo_producao(producao),
                    hide_index=True, height=ALTURA_PRODUCAO,
                    on_select="rerun", selection_mode="single-row",
                    key=f"tab_producao_{versao}")

            linhas_sel = list(evento.selection.rows) if evento is not None else []
            idx = linhas_sel[0] if linhas_sel and linhas_sel[0] < len(chaves) else None
            chave_sel = chaves[idx] if idx is not None else None
            chave_em_prod = em_prod["chave"] if em_prod else None

            with area_botoes:
                pode_iniciar = chave_sel is not None and em_prod is None
                pode_finalizar = chave_sel is not None and chave_sel == chave_em_prod
                c1, c2, c3 = st.columns([1.2, 1.2, 4])
                iniciar = c1.button("INICIAR PRODUÇÃO", type="primary",
                                    disabled=not pode_iniciar, key="btn_iniciar")
                finalizar = c2.button("FINALIZAR PEDIDO", disabled=not pode_finalizar,
                                      key="btn_finalizar")
                with c3:
                    if chave_sel is None:
                        dica = "Selecione um pedido na tabela."
                    elif em_prod is not None and chave_sel != chave_em_prod:
                        dica = ("Já existe um pedido em produção. Finalize-o (1ª linha) "
                                "antes de iniciar outro.")
                    elif em_prod is not None:
                        dica = "Pedido em produção selecionado: pode ser finalizado."
                    else:
                        dica = "Pedido selecionado: pode ser iniciado."
                    st.caption(dica)
                if chave_sel is not None:
                    _detalhes(estado["pedidos_por_chave"][chave_sel], producao.iloc[idx])

            if iniciar and pode_iniciar:
                ped = estado["pedidos_por_chave"][chave_sel]
                _confirmar("iniciar", servico.registro_para_iniciar(ped), banco, agora)
            if finalizar and pode_finalizar:
                _confirmar("finalizar",
                           {"chave": em_prod["chave"], "cliente": em_prod["cliente"],
                            "produto": em_prod["produto"], "quantidade": em_prod["quantidade"]},
                           banco, agora)

    with aba_concluidos:
        with st.container(border=True):
            st.markdown('<div class="titulo-painel">PEDIDOS CONCLUÍDOS</div>'
                        '<div class="sub-painel">Histórico dos pedidos finalizados, '
                        'incluindo o tempo real de produção.</div>', unsafe_allow_html=True)
            if estado["concluidos"].empty:
                st.info("Nenhum pedido concluído ainda.")
            else:
                _tabela(_estilo_concluidos(estado["concluidos"]),
                        hide_index=True, height=ALTURA_CONCLUIDOS)

    # ---- informações de apoio ----
    with st.expander("Produtos cadastrados (produtos.json, somente leitura)"):
        _tabela(servico.tabela_produtos(), hide_index=True)
    if estado["ignorados"]:
        with st.expander(f"Linhas da planilha ignoradas por erro de preenchimento "
                         f"({len(estado['ignorados'])})"):
            import pandas as pd
            _tabela(pd.DataFrame(estado["ignorados"]), hide_index=True)

    _vigia(banco)
