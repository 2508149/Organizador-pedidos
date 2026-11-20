"""
servico.py - Junta planilha + banco + algoritmo e entrega o estado pronto
para a interface (sem nenhum código de Streamlit, para poder ser testado).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from pedidos import (carregar_produtos, montar_pedidos, normalizar_texto,
                     pedido_de_registro)
from planejador import LIMITE_ATRASO_DIAS, classificar_atraso, planejar_com_fixado

FUSO = ZoneInfo("America/Sao_Paulo")
COL_LIMITE = f"Limite (+{LIMITE_ATRASO_DIAS} dias)"


def agora_sp():
    """Momento atual em São Paulo, sem segundos (igual ao notebook)."""
    return datetime.now(FUSO).replace(second=0, microsecond=0, tzinfo=None)


def tabela_produtos():
    """Produtos cadastrados no JSON (somente leitura) como DataFrame."""
    return pd.DataFrame([
        {"ID": p.id, "Produto": p.nome, "Tempo unitário (min)": p.tempo_unitario}
        for p in carregar_produtos()
    ])


def _fmt_ts(texto):
    return datetime.fromisoformat(texto).strftime("%d/%m/%Y %H:%M")


def _fmt_duracao(inicio, fim):
    """Formata o tempo real entre início e conclusão do pedido."""
    segundos = max(0, int((datetime.fromisoformat(fim) -
                           datetime.fromisoformat(inicio)).total_seconds()))
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)
    prefixo = f"{dias}d " if dias else ""
    return f"{prefixo}{horas:02d}:{minutos:02d}:{segundos:02d}"


def montar_estado(df_pedidos, banco, agora=None):
    """Monta tudo o que a tela exibe.

    Retorna dict com: producao (DataFrame), chaves (lista alinhada às linhas
    de producao), concluidos (DataFrame), ignorados (lista), resumo, kpis,
    em_producao (registro ou None) e registro_por_chave.
    """
    agora = agora or agora_sp()
    hoje = agora.date()

    mapa_produtos = {normalizar_texto(p.nome): p for p in carregar_produtos()}

    registros = banco.listar()
    em_producao = next((r for r in registros if r['status'] == 'em_producao'), None)
    concluidos = [r for r in registros if r['status'] == 'concluido']
    chaves_no_banco = {r['chave'] for r in registros}

    gerenciador, ignorados = montar_pedidos(
        df_pedidos, mapa_produtos, hoje, chaves_no_banco)

    fixado, inicio_fixado = None, None
    if em_producao:
        fixado = pedido_de_registro(em_producao, mapa_produtos, id_pedido=0)
        inicio_fixado = datetime.fromisoformat(
            em_producao['iniciado_em']).replace(second=0, microsecond=0)

    res = planejar_com_fixado(gerenciador.lista_peds, agora, fixado, inicio_fixado)

    # ---- tabela PEDIDOS EM PRODUÇÃO (colunas calculadas pelo algoritmo) ----
    linhas, chaves, registro_por_chave = [], [], {}
    for posicao, (ped, lin) in enumerate(zip(res['sequencia'], res['linhas']), 1):
        iniciado = fixado is not None and ped is fixado
        linhas.append({
            "Prioridade": posicao,
            "Cliente": lin["Cliente"],
            "Produto": lin["Produto"],
            "Quantidade": lin["Quantidade"],
            "Tempo total (min)": lin["Tempo total (min)"],
            "Data de entrega": lin["Data de entrega"],
            COL_LIMITE: lin[COL_LIMITE],
            "Início da produção": lin["Início da produção"],
            "Conclusão": lin["Conclusão"],
            "Dias de atraso": lin["Dias de atraso"],
            "Dias além do limite": lin["Dias além do limite"],
            "Situação": lin["Situação"],
            "Status": "● EM PRODUÇÃO" if iniciado else "Aguardando",
        })
        chaves.append(ped.chave)
        registro_por_chave[ped.chave] = {
            "linha": getattr(ped, "linha", None), "registro": ped.chave}
    producao = pd.DataFrame(linhas)

    # ---- tabela PEDIDOS CONCLUÍDOS (dados do instantâneo preservado) ----
    linhas_c = []
    for r in sorted(concluidos, key=lambda x: x['concluido_em'], reverse=True):
        entrega = datetime.fromisoformat(r['data_entrega']).date()
        fim = datetime.fromisoformat(r['concluido_em'])
        atraso = max(0, (fim.date() - entrega).days)
        linhas_c.append({
            "Cliente": r['cliente'],
            "Produto": r['produto'],
            "Quantidade": r['quantidade'],
            "Tempo total (min)": r['tempo_total'],
            "Data de entrega": entrega.strftime("%d/%m/%Y"),
            "Iniciado em": _fmt_ts(r['iniciado_em']),
            "Concluído em": _fmt_ts(r['concluido_em']),
            "Tempo de produção": _fmt_duracao(r['iniciado_em'], r['concluido_em']),
            "Situação": classificar_atraso(atraso)[0],
            "Status": "✔ CONCLUÍDO",
        })
    df_concluidos = pd.DataFrame(linhas_c)

    resumo = res['resumo']
    atrasados = (resumo['atrasados_dentro_limite'] + resumo['acima_limite']) if resumo else 0
    kpis = {
        "em_producao": len(producao),
        "concluidos": len(concluidos),
        "atrasados": atrasados,
        "acima_limite": resumo['acima_limite'] if resumo else 0,
        "em_andamento": em_producao['cliente'] if em_producao else None,
    }

    return {
        "producao": producao,
        "chaves": chaves,
        "registro_por_chave": registro_por_chave,
        "concluidos": df_concluidos,
        "ignorados": ignorados,
        "resumo": resumo,
        "kpis": kpis,
        "em_producao": em_producao,
        "pedidos_por_chave": {p.chave: p for p in res['sequencia']},
    }


def registro_para_iniciar(ped):
    """Instantâneo do pedido, no formato que o banco grava ao iniciar."""
    return {
        "chave": ped.chave,
        "cliente": ped.cliente,
        "produto": ped.produto.nome,
        "quantidade": ped.quantidade,
        "data_entrega": ped.data_entrega.isoformat(),
        "tempo_total": ped.tempo_total,
        "linha_planilha": getattr(ped, "linha", None),
    }
