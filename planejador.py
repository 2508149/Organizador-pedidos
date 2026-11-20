"""
planejador.py - Calendário de produção e algoritmo de planejamento.

As seções "Calendário", "Algoritmo de otimização" e "Avaliação da sequência"
abaixo são CÓPIAS LITERAIS das células 7, 8 e 9 do notebook
Organizador_Pedidos_Limite_10_Dias.ipynb. Nenhuma regra de cálculo ou de
priorização foi alterada.

A única adição está no final do arquivo (planejar_com_fixado) e serve para
manter o pedido já iniciado na primeira posição.
"""
import heapq
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, time, date


# =====================================================================
# 7. Funções de calendário e horário de produção (notebook, célula 7)
# =====================================================================
HORA_INI = time(8, 0)
HORA_ALMOCO = time(12, 0)
HORA_RETORNO = time(13, 0)
HORA_FIM = time(17, 0)
JANELAS = [(HORA_INI, HORA_ALMOCO), (HORA_RETORNO, HORA_FIM)]

LIMITE_ATRASO_DIAS = 10   # atraso máximo permitido, em dias corridos


def eh_dia_util(dia):
    return dia.weekday() < 5     # 0 = segunda ... 4 = sexta


def ajustar_inicio(inicio):
    # Avança para o próximo instante permitido: dia útil, dentro do expediente
    # e fora do almoço. Se já for permitido, devolve o mesmo valor.
    while True:
        if not eh_dia_util(inicio.date()):
            inicio = datetime.combine(inicio.date() + timedelta(days=1), HORA_INI)
        elif inicio.time() < HORA_INI:
            inicio = datetime.combine(inicio.date(), HORA_INI)
        elif HORA_ALMOCO <= inicio.time() < HORA_RETORNO:
            inicio = datetime.combine(inicio.date(), HORA_RETORNO)
        elif inicio.time() >= HORA_FIM:
            inicio = datetime.combine(inicio.date() + timedelta(days=1), HORA_INI)
        else:
            return inicio


def calc_conclu(inicio, temp_produ):
    # Retorna (inicio_real, conclusao).
    # A produção é consumida em blocos (manhã/tarde), pulando almoço,
    # noites e fins de semana. O pedido não é interrompido por escolha,
    # apenas "espera" o próximo bloco quando o expediente acaba.
    if temp_produ < 0:
        raise ValueError("O tempo de produção não pode ser negativo.")

    inicio_real = ajustar_inicio(inicio)
    atual = inicio_real
    restante = temp_produ

    while restante > 0:
        atual = ajustar_inicio(atual)
        # Limite do bloco atual: almoço (manhã) ou fim do expediente (tarde).
        hora_limite = HORA_ALMOCO if atual.time() < HORA_ALMOCO else HORA_FIM
        limite = datetime.combine(atual.date(), hora_limite)
        disponivel = (limite - atual).total_seconds() / 60

        if restante <= disponivel:
            atual += timedelta(minutes=restante)
            restante = 0
        else:
            atual = limite
            restante -= disponivel

    return inicio_real, atual


def minutos_uteis_do_dia(dia, a_partir_de=None):
    # Minutos produtivos de um dia (480 em dia útil completo).
    # Se a_partir_de for informado, conta apenas do horário em diante.
    if not eh_dia_util(dia):
        return 0
    total = 0
    for ini, fim in JANELAS:
        ini_min = ini.hour * 60 + ini.minute
        fim_min = fim.hour * 60 + fim.minute
        if a_partir_de is not None:
            ref = a_partir_de.hour * 60 + a_partir_de.minute + a_partir_de.second / 60
            ini_min = max(ini_min, ref)
        total += max(0, fim_min - ini_min)
    return total


def gerar_calendario(inicio_real, total_minutos):
    # Lista os dias úteis a partir do início e os minutos produtivos acumulados
    # ao FIM de cada um deles, até cobrir total_minutos.
    datas, acumulado = [], []
    soma = 0
    dia = inicio_real.date()
    primeiro = True
    while True:
        minutos = minutos_uteis_do_dia(dia, inicio_real.time() if primeiro else None)
        primeiro = False
        if minutos > 0:
            soma += minutos
            datas.append(dia)
            acumulado.append(soma)
            if soma >= total_minutos:
                return datas, acumulado
        dia += timedelta(days=1)


def prazo_em_minutos(data_entrega, datas, acumulado):
    # Converte a data de entrega no prazo em minutos produtivos: tudo o que
    # cabe desde o início do planejamento até as 17:00 do último dia útil
    # menor ou igual à data de entrega. Fim de semana => vale a sexta anterior.
    i = bisect_right(datas, data_entrega) - 1
    return 0 if i < 0 else acumulado[i]


def data_conclusao(minutos_acumulados, datas, acumulado):
    # Dia em que o pedido termina, dado o total de minutos produtivos
    # já consumidos (incluindo ele). Terminar às 17:00 conta como o próprio dia.
    i = min(bisect_left(acumulado, minutos_acumulados), len(datas) - 1)
    return datas[i]


# =====================================================================
# 8. Algoritmo de otimização (notebook, célula 8)
# =====================================================================
def avaliar_rapido(sequencia, datas, acumulado, limite_dias=LIMITE_ATRASO_DIAS):
    # Avaliação leve usada dentro da busca. Retorna a tupla de critérios, que é
    # comparada de forma LEXICOGRÁFICA (menor é melhor; o anterior sempre vence):
    #   1) pedidos com atraso acima do limite
    #   2) maior excesso (dias além do limite)
    #   3) soma dos excessos (dias além do limite)
    #   4) pedidos atrasados (qualquer atraso)
    #   5) soma dos dias corridos de atraso
    #   6) soma dos tempos de conclusão (minutos produtivos)
    soma = 0
    acima_limite = 0
    maior_excesso = 0
    soma_excesso = 0
    atrasados = 0
    dias_atraso = 0
    soma_conclu = 0
    for ped in sequencia:
        soma += ped.tempo_total
        atraso = (data_conclusao(soma, datas, acumulado) - ped.data_entrega).days
        if atraso > 0:
            atrasados += 1
            dias_atraso += atraso
            excesso = atraso - limite_dias
            if excesso > 0:
                acima_limite += 1
                soma_excesso += excesso
                if excesso > maior_excesso:
                    maior_excesso = excesso
        soma_conclu += soma
    return (acima_limite, maior_excesso, soma_excesso,
            atrasados, dias_atraso, soma_conclu)


def moore_hodgson(pedidos, prazos):
    # prazos: dicionário {id_do_pedido: prazo em minutos produtivos}.
    # Aqui os prazos recebidos já são os AMPLIADOS (entrega + 10 dias corridos),
    # então "atrasado" significa "acima do limite de 10 dias".
    # Retorna (pedidos_no_prazo em ordem de entrega, pedidos_atrasados).
    chave = lambda p: (prazos[p.id], p.tempo_total, p.id)
    heap = []                 # guarda (-tempo, id, pedido): o topo é o MAIOR tempo
    soma = 0
    atrasados = []

    for ped in sorted(pedidos, key=chave):
        heapq.heappush(heap, (-ped.tempo_total, ped.id, ped))
        soma += ped.tempo_total
        if soma > prazos[ped.id]:
            _, _, maior = heapq.heappop(heap)
            soma -= maior.tempo_total
            atrasados.append(maior)

    no_prazo = sorted((item[2] for item in heap), key=chave)
    return no_prazo, atrasados


def melhorar_sequencia(sequencia, avaliar, max_avaliacoes=20000):
    # Busca local: para CADA pedido, testa todas as outras posições da sequência
    # e o move para a MELHOR posição encontrada, se ela melhorar o critério
    # (tupla comparada lexicograficamente). Repete até não haver melhoria ou
    # até atingir o limite de avaliações. Como só aceita melhorias
    # lexicográficas, os critérios de maior prioridade nunca pioram.
    # Heurística: pode parar em ótimo local.
    atual = list(sequencia)
    criterio = avaliar(atual)
    usadas = 0
    melhorou = True
    while melhorou and usadas < max_avaliacoes:
        melhorou = False
        for ped in list(atual):
            i = atual.index(ped)
            resto = atual[:i] + atual[i + 1:]
            melhor_seq, melhor_crit = None, criterio
            for j in range(len(atual)):
                if j == i:
                    continue
                if usadas >= max_avaliacoes:
                    break
                candidata = resto[:j] + [ped] + resto[j:]
                novo = avaliar(candidata)
                usadas += 1
                if novo < melhor_crit:
                    melhor_seq, melhor_crit = candidata, novo
            if melhor_seq is not None:
                atual, criterio = melhor_seq, melhor_crit
                melhorou = True
            if usadas >= max_avaliacoes:
                return atual, criterio
    return atual, criterio


def planejar(pedidos, inicio_planejamento, max_avaliacoes=20000,
             limite_dias=LIMITE_ATRASO_DIAS):
    # Etapas: calendário -> prazos AMPLIADOS (entrega + limite_dias corridos)
    # em minutos produtivos -> Moore-Hodgson (mínimo de pedidos acima do limite)
    # -> sequências iniciais candidatas -> busca local nos demais critérios.
    inicio_real = ajustar_inicio(inicio_planejamento)
    total = sum(p.tempo_total for p in pedidos)
    datas, acumulado = gerar_calendario(inicio_real, total)

    prazos_orig = {p.id: prazo_em_minutos(p.data_entrega, datas, acumulado)
                   for p in pedidos}
    prazos = {p.id: prazo_em_minutos(p.data_entrega + timedelta(days=limite_dias),
                                     datas, acumulado)
              for p in pedidos}

    no_prazo, atrasados = moore_hodgson(pedidos, prazos)

    # Os pedidos que estouram o limite vão para o fim (nenhum é descartado).
    # Duas ordens para o "fundo da fila": menor tempo primeiro (SPT) ou menor
    # prazo ampliado primeiro (EDD); fica a de melhor critério.
    cauda_spt = sorted(atrasados, key=lambda p: (p.tempo_total, prazos[p.id], p.id))
    cauda_edd = sorted(atrasados, key=lambda p: (prazos[p.id], p.tempo_total, p.id))

    avaliar = lambda seq: avaliar_rapido(seq, datas, acumulado, limite_dias)
    cands_mh = [no_prazo + cauda_spt, no_prazo + cauda_edd]
    seq_mh = min(cands_mh, key=avaliar)
    crit_mh = avaliar(seq_mh)

    # Ponto de partida extra: ordem simples por data de entrega original.
    seq_edd = sorted(pedidos, key=lambda p: (prazos_orig[p.id], p.tempo_total, p.id))
    seq_ini = min([seq_mh, seq_edd], key=avaliar)
    crit_ini = avaliar(seq_ini)

    seq_final, crit_final = melhorar_sequencia(seq_ini, avaliar, max_avaliacoes)

    # Nenhum pedido pode ser descartado.
    if sorted(p.id for p in seq_final) != sorted(p.id for p in pedidos):
        raise RuntimeError("A otimização descartou ou duplicou pedidos.")

    return {
        'sequencia': seq_final,
        'criterio': crit_final,
        'sequencia_mh': seq_mh,
        'criterio_mh': crit_mh,
        'sequencia_inicial': seq_ini,
        'criterio_inicial': crit_ini,
        'prazos': prazos,                  # prazos ampliados (minutos produtivos)
        'prazos_originais': prazos_orig,
        'limite_dias': limite_dias,
        # Mínimo de pedidos que ultrapassam o limite (EXATO, via Moore-Hodgson).
        'min_acima_limite': crit_mh[0],
        'viavel': crit_mh[0] == 0,
        'avaliar': avaliar,
    }


# =====================================================================
# 9. Avaliação da sequência (notebook, célula 9)
# =====================================================================
def classificar_atraso(atras_dias, limite_dias=LIMITE_ATRASO_DIAS):
    # Traduz os dias de atraso na situação do pedido.
    # Retorna (situacao, dias_alem_do_limite).
    if atras_dias <= 0:
        return "No prazo", 0
    if atras_dias <= limite_dias:           # exatamente 10 dias ainda é permitido
        return "Atrasado — dentro do limite", 0
    excesso = atras_dias - limite_dias
    unidade = "dia" if excesso == 1 else "dias"
    return f"Limite ultrapassado em {excesso} {unidade}", excesso


def aval_sequencia(sequencia, inicio_producao, limite_dias=LIMITE_ATRASO_DIAS):
    # Retorna (criterio, linhas): criterio é a mesma tupla de 6 critérios de
    # avaliar_rapido() e linhas é a lista de dicionários para a tabela.
    ini = ajustar_inicio(inicio_producao)
    linhas = []
    acima_limite = 0
    maior_excesso = 0
    soma_excesso = 0
    quant_atras = 0
    atras_total = 0
    soma_conclu = 0
    acumulado = 0

    for ped in sequencia:
        inicio_ped, conclusao = calc_conclu(ini, ped.tempo_total)

        atras_dias = max(0, (conclusao.date() - ped.data_entrega).days)
        situacao, excesso = classificar_atraso(atras_dias, limite_dias)

        if atras_dias > 0:
            quant_atras += 1
            atras_total += atras_dias
        if excesso > 0:
            acima_limite += 1
            soma_excesso += excesso
            maior_excesso = max(maior_excesso, excesso)

        acumulado += ped.tempo_total
        soma_conclu += acumulado

        prazo_limite = ped.data_entrega + timedelta(days=limite_dias)
        linhas.append({
            "ID": ped.id,
            "Cliente": ped.cliente,
            "Produto": ped.produto.nome,
            "Quantidade": ped.quantidade,
            "Tempo total (min)": ped.tempo_total,
            "Data de entrega": ped.data_entrega.strftime("%d/%m/%Y"),
            f"Limite (+{limite_dias} dias)": prazo_limite.strftime("%d/%m/%Y"),
            "Início da produção": inicio_ped.strftime("%d/%m/%Y %H:%M"),
            "Conclusão": conclusao.strftime("%d/%m/%Y %H:%M"),
            "Dias de atraso": atras_dias,
            "Dias além do limite": excesso,
            "Situação": situacao,
        })

        ini = conclusao     # o próximo pedido começa quando este termina

    criterio = (acima_limite, maior_excesso, soma_excesso,
                quant_atras, atras_total, soma_conclu)
    return criterio, linhas


def resumir_resultado(linhas, limite_dias=LIMITE_ATRASO_DIAS):
    # Resumo geral a partir das linhas da tabela final.
    atrasos = [l["Dias de atraso"] for l in linhas]
    maior = max(atrasos, default=0)
    acima = sum(1 for l in linhas if l["Dias além do limite"] > 0)
    atrasados = sum(1 for a in atrasos if a > 0)
    return {
        'total': len(linhas),
        'no_prazo': len(linhas) - atrasados,
        'atrasados_dentro_limite': atrasados - acima,
        'acima_limite': acima,
        'maior_atraso': maior,
        'maior_excesso': max(0, maior - limite_dias),
        'regra_respeitada': acima == 0,
        'limite_dias': limite_dias,
    }


# =====================================================================
# ADIÇÃO PARA A VERSÃO WEB (NÃO existe no notebook)
# =====================================================================
def planejar_com_fixado(pedidos, agora, fixado=None, inicio_fixado=None):
    """Planeja a produção mantendo o pedido já iniciado na 1ª posição.

    - Sem pedido fixado: equivale exatamente ao fluxo do notebook
      (planejar + aval_sequencia a partir de `agora`).
    - Com pedido fixado: ele ocupa a posição 1 e NÃO entra no algoritmo.
      Os demais são planejados pelo `planejar()` original, começando quando
      o fixado termina (ou em `agora`, se o término previsto já passou, pois
      não é possível planejar no passado).

    Retorna dict com: sequencia, linhas, plano (ou None), resumo (ou None).
    """
    if fixado is None:
        inicio_resto = agora
        linhas_fixado = []
    else:
        _, conclusao_fixado = calc_conclu(inicio_fixado, fixado.tempo_total)
        inicio_resto = max(conclusao_fixado, agora)
        _, linhas_fixado = aval_sequencia([fixado], inicio_fixado)

    if pedidos:
        plano = planejar(pedidos, inicio_resto)
        criterio_det, linhas_resto = aval_sequencia(plano['sequencia'], inicio_resto)

        # Mesmas conferências do notebook (seção 10).
        assert [l["ID"] for l in linhas_resto] == [p.id for p in plano['sequencia']], \
            "A tabela não segue a sequência calculada."
        assert criterio_det == plano['criterio'], \
            "Avaliação detalhada diverge da usada na otimização."
        assert len(linhas_resto) == len(pedidos), \
            "Algum pedido foi descartado durante a otimização."
        sequencia_resto = list(plano['sequencia'])
    else:
        plano, linhas_resto, sequencia_resto = None, [], []

    sequencia = ([fixado] if fixado is not None else []) + sequencia_resto
    linhas = linhas_fixado + linhas_resto
    return {
        'sequencia': sequencia,
        'linhas': linhas,
        'plano': plano,
        'resumo': resumir_resultado(linhas) if linhas else None,
        'inicio_resto': inicio_resto,
    }
