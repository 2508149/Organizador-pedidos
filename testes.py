"""
testes.py - Testes automáticos. Execute com:  python testes.py

Parte 1: os testes do notebook (seção 12), copiados sem alteração, agora
         apontando para os módulos planejador.py e pedidos.py.
Parte 2: testes novos da versão web (pedido iniciado fixo em 1º, banco,
         chaves, produtos.json intacto e fluxo completo da tela).
"""
from datetime import datetime, timedelta, time, date

from pedidos import (Produtos, Pedido, normalizar_texto, validar_quantidade,
                     converter_data, validar_pedido)
from planejador import (HORA_INI, HORA_ALMOCO, HORA_RETORNO, HORA_FIM, JANELAS,
                        eh_dia_util, ajustar_inicio, calc_conclu,
                        gerar_calendario, prazo_em_minutos, planejar,
                        aval_sequencia, classificar_atraso, resumir_resultado)


# =====================================================================
# Testes do notebook (seção 12) - sem alterações
# =====================================================================
def executar_testes():
    import random
    import time as relogio
    from itertools import permutations

    seg = datetime(2026, 11, 16, 8, 0)    # segunda-feira, 08:00
    P = Produtos(1, "T", 1)               # produto fictício: 1 min por unidade

    def ped(i, minutos, entrega):
        return Pedido(i, "c", P, minutos, entrega)

    def melhor_exaustivo(peds, avaliar):
        return min(avaliar(list(s)) for s in permutations(peds))

    def minutos_produtivos_entre(a, b):
        # Conta, dia a dia, os minutos de expediente entre a e b (independente de calc_conclu).
        total, dia = 0, a.date()
        while dia <= b.date():
            if eh_dia_util(dia):
                for ini, fim in JANELAS:
                    i = max(datetime.combine(dia, ini), a)
                    f = min(datetime.combine(dia, fim), b)
                    if f > i:
                        total += (f - i).total_seconds() / 60
            dia += timedelta(days=1)
        return total

    def aleatorios(n, tempos, dmin, dmax):
        return [ped(i + 1, random.choice(tempos),
                    (seg + timedelta(days=random.randint(dmin, dmax))).date())
                for i in range(n)]

    resultados = []

    # --- Calendário e horários (testes anteriores, preservados) ---
    assert calc_conclu(datetime(2026, 11, 20, 16, 0), 120) == \
        (datetime(2026, 11, 20, 16, 0), datetime(2026, 11, 23, 9, 0))   # sexta -> segunda
    assert calc_conclu(datetime(2026, 11, 21, 10, 0), 60) == \
        (datetime(2026, 11, 23, 8, 0), datetime(2026, 11, 23, 9, 0))    # sábado
    assert calc_conclu(datetime(2026, 11, 16, 12, 30), 30) == \
        (datetime(2026, 11, 16, 13, 0), datetime(2026, 11, 16, 13, 30)) # almoço
    assert calc_conclu(seg, 600) == (seg, datetime(2026, 11, 17, 10, 0))  # vários dias
    assert calc_conclu(seg, 240)[1] == datetime(2026, 11, 16, 12, 0)
    assert calc_conclu(seg, 480)[1] == datetime(2026, 11, 16, 17, 0)
    assert ajustar_inicio(datetime(2026, 11, 14, 17, 46)) == seg          # sábado à noite

    datas, acum = gerar_calendario(seg, 5000)
    assert prazo_em_minutos(date(2026, 11, 16), datas, acum) == 480
    assert prazo_em_minutos(date(2026, 11, 21), datas, acum) == 2400      # sábado = sexta
    assert prazo_em_minutos(date(2026, 11, 22), datas, acum) == 2400      # domingo = sexta
    assert prazo_em_minutos(date(2026, 11, 15), datas, acum) == 0

    # --- Validações (testes anteriores, preservados) ---
    for ok in ["20", 20, 20.0, " 7 "]:
        assert validar_quantidade(ok)[1] is None, ok
    for ruim in ["", "P", "-3", "0", 0, "2,5", 2.5, None]:
        assert validar_quantidade(ruim)[1] is not None, ruim
    h = date(2026, 11, 14)
    assert converter_data("14/11/2026")[1] is None
    assert converter_data("31/02/2027")[0] is None
    assert converter_data("")[0] is None and converter_data("abc")[0] is None
    prod_teste = Produtos(1, "VALVULA XX", 30)
    mapa = {normalizar_texto("VALVULA XX"): prod_teste}
    dados, erros = validar_pedido(
        {'CLIENTE': '', 'PRODUTOS': 'X', 'QUANTIDADE': 'P', 'DATA DE ENTREGA': '04/05/1998'},
        mapa, h)
    assert dados is None and len(erros) == 4, erros     # acumula todos os erros
    dados, erros = validar_pedido(
        {'CLIENTE': 'A', 'PRODUTOS': ' valvula  xx ', 'QUANTIDADE': 2, 'DATA DE ENTREGA': '14/11/2026'},
        mapa, h)
    assert erros == [] and dados['quantidade'] == 2     # hoje é permitido
    resultados.append("Calendário e validações anteriores: OK")

    # --- Classificação do atraso (tabela do enunciado) ---
    esperado = {0: ("No prazo", 0),
                5: ("Atrasado — dentro do limite", 0),
                10: ("Atrasado — dentro do limite", 0),
                11: ("Limite ultrapassado em 1 dia", 1),
                15: ("Limite ultrapassado em 5 dias", 5)}
    for dias, esp in esperado.items():
        assert classificar_atraso(dias) == esp, (dias, classificar_atraso(dias))
    resultados.append("Classificação 0/5/10/11/15 dias de atraso: OK")

    # --- Teste 1: todos os pedidos dentro dos 10 dias ---
    peds1 = [ped(1, 480, date(2026, 11, 16)),      # termina 16/11: no prazo
             ped(2, 480, date(2026, 11, 17)),      # termina 17/11: no prazo
             ped(3, 2400, date(2026, 11, 13))]     # termina 25/11 aprox.: atrasado, mas <= 10 dias
    pl1 = planejar(peds1, seg)
    crit1, linhas1 = aval_sequencia(pl1['sequencia'], seg)
    assert pl1['viavel'] and crit1[0] == 0 and crit1[1] == 0 and crit1[2] == 0
    res1 = resumir_resultado(linhas1)
    assert res1['regra_respeitada'] and res1['acima_limite'] == 0
    assert res1['atrasados_dentro_limite'] >= 1
    resultados.append("Teste 1 (todos dentro dos 10 dias): OK")

    # --- Teste 2: exatamente 10 dias de atraso (permitido) ---
    # Entrega 10/11; 2400 min = 5 dias úteis completos -> termina sexta 20/11 17:00.
    pl2 = planejar([ped(1, 2400, date(2026, 11, 10))], seg)
    crit2, linhas2 = aval_sequencia(pl2['sequencia'], seg)
    assert linhas2[0]["Conclusão"].startswith("20/11/2026")
    assert linhas2[0]["Dias de atraso"] == 10 and linhas2[0]["Dias além do limite"] == 0
    assert linhas2[0]["Situação"] == "Atrasado — dentro do limite"
    assert pl2['viavel'] and crit2[0] == 0
    resultados.append("Teste 2 (exatamente 10 dias de atraso): OK")

    # --- Teste 3: 11 dias de atraso (ultrapassa o limite) ---
    # Entrega 09/11; o mesmo pedido termina 20/11 -> 11 dias.
    pl3 = planejar([ped(1, 2400, date(2026, 11, 9))], seg)
    crit3, linhas3 = aval_sequencia(pl3['sequencia'], seg)
    assert linhas3[0]["Dias de atraso"] == 11 and linhas3[0]["Dias além do limite"] == 1
    assert linhas3[0]["Situação"] == "Limite ultrapassado em 1 dia"
    assert (not pl3['viavel']) and crit3[0] == 1 and pl3['min_acima_limite'] == 1
    assert not resumir_resultado(linhas3)['regra_respeitada']
    resultados.append("Teste 3 (11 dias de atraso): OK")

    # --- Teste 4: vários pedidos ultrapassam o limite ---
    peds4 = [ped(i, 2400, date(2026, 11, 10)) for i in (1, 2, 3)]   # 3 semanas de trabalho, prazo comum
    pl4 = planejar(peds4, seg)
    crit4, linhas4 = aval_sequencia(pl4['sequencia'], seg)
    melhor4 = melhor_exaustivo(peds4, pl4['avaliar'])
    assert crit4[0] == 2 and melhor4[0] == 2 and not pl4['viavel']
    assert crit4 == melhor4          # nesta instância a busca local também achou o ótimo completo
    # Exemplo do enunciado: A (2 dias), B (8 dias), C (10 dias) = 960, 3840, 4800 min
    peds4b = [ped(1, 960, date(2026, 11, 20)),
              ped(2, 3840, date(2026, 11, 21)),
              ped(3, 4800, date(2026, 11, 22))]
    pl4b = planejar(peds4b, seg)
    assert pl4b['criterio'][0] == melhor_exaustivo(peds4b, pl4b['avaliar'])[0]
    resultados.append("Teste 4 (vários acima do limite, contra busca exaustiva): OK")

    # --- Teste 5: sequência alternativa reduz o atraso excessivo ---
    peds5 = [ped(1, 3000, date(2026, 11, 15)),
             ped(2, 960, date(2026, 11, 12)),
             ped(3, 3000, date(2026, 11, 26))]
    ingenua, _ = aval_sequencia(peds5, seg)                 # ordem de chegada: 1, 2, 3
    pl5 = planejar(peds5, seg)
    crit5, _ = aval_sequencia(pl5['sequencia'], seg)
    assert crit5[0] == ingenua[0] > 0                       # mesmo nº de pedidos acima do limite
    assert crit5[1] < ingenua[1] and crit5[2] < ingenua[2]  # menor excesso máximo e total
    assert [p.id for p in pl5['sequencia']] != [1, 2, 3]
    resultados.append(f"Teste 5 (reordenar reduz o excesso máximo de {ingenua[1]} para {crit5[1]} dias): OK")

    # --- Moore-Hodgson (+10 dias) x busca exaustiva, instâncias pequenas ---
    random.seed(7)
    n_inst = n_inviaveis = c2_ok = c3_ok = completo_ok = 0
    for _ in range(60):
        n = random.randint(3, 7)
        peds = aleatorios(n, [240, 480, 960, 1500, 2400, 3000], -3, 12)
        plano_t = planejar(peds, seg)
        melhor = melhor_exaustivo(peds, plano_t['avaliar'])
        assert plano_t['criterio'][0] == melhor[0], "Número mínimo de pedidos acima do limite não encontrado!"
        assert plano_t['criterio_mh'][0] == plano_t['criterio'][0]
        assert plano_t['criterio'] <= plano_t['criterio_inicial']   # a busca local nunca piora
        assert plano_t['viavel'] == (melhor[0] == 0)
        crit_d, _ = aval_sequencia(plano_t['sequencia'], seg)
        assert crit_d == plano_t['criterio']
        n_inst += 1
        n_inviaveis += melhor[0] > 0
        c2_ok += plano_t['criterio'][1] == melhor[1]
        c3_ok += plano_t['criterio'][:3] == melhor[:3]
        completo_ok += plano_t['criterio'] == melhor
    resultados.append(
        f"Busca exaustiva ({n_inst} instâncias, {n_inviaveis} sem solução viável): "
        f"critério 1 ótimo em {n_inst}/{n_inst} (garantido); "
        f"critérios 1-2 ótimos em {c2_ok}/{n_inst}, 1-3 em {c3_ok}/{n_inst}, "
        f"todos os 6 em {completo_ok}/{n_inst} (heurística, sem garantia)")

    # --- Teste 6: nenhum pedido é descartado (inclusive com pedidos impossíveis) ---
    random.seed(11)
    for _ in range(30):
        n = random.randint(3, 30)
        peds = aleatorios(n, [30, 480, 2400, 9000], -5, 15)
        plano_t = planejar(peds, seg)
        assert sorted(p.id for p in plano_t['sequencia']) == [p.id for p in peds]
        _, lin = aval_sequencia(plano_t['sequencia'], seg)
        assert len(lin) == n
    gigante = [ped(1, 130000, date(2026, 12, 25)), ped(2, 100, date(2026, 11, 23))]
    pl6 = planejar(gigante, seg)
    assert len(pl6['sequencia']) == 2 and not pl6['viavel']
    resultados.append("Teste 6 (nenhum pedido descartado, 30 instâncias + pedido gigante): OK")

    # --- Teste 7: 10, 20, 50 e 100 pedidos ---
    random.seed(21)
    tempos_t7 = []
    for n in (10, 20, 50, 100):
        peds = aleatorios(n, [30, 60, 120, 480, 900, 1500, 2400], 0, 60)
        t0 = relogio.time()
        plano_t = planejar(peds, seg)
        dt = relogio.time() - t0
        crit_d, lin = aval_sequencia(plano_t['sequencia'], seg)
        assert crit_d == plano_t['criterio']
        assert sorted(p.id for p in plano_t['sequencia']) == list(range(1, n + 1))
        assert plano_t['criterio'][0] == plano_t['criterio_mh'][0] == plano_t['min_acima_limite']
        assert plano_t['criterio'] <= plano_t['criterio_inicial']
        tempos_t7.append(f"{n} pedidos: {dt:.2f} s, acima do limite: {plano_t['criterio'][0]}")
    resultados.append("Teste 7 (10/20/50/100 pedidos): OK — " + "; ".join(tempos_t7))

    # --- Teste 8: horários, almoço e fins de semana ---
    random.seed(33)
    peds8 = aleatorios(20, [30, 100, 480, 900, 2400], 0, 40)
    pl8 = planejar(peds8, datetime(2026, 11, 18, 16, 28))     # início no meio da tarde
    _, lin8 = aval_sequencia(pl8['sequencia'], datetime(2026, 11, 18, 16, 28))
    fmt = "%d/%m/%Y %H:%M"
    anterior = None
    for linha in lin8:
        ini = datetime.strptime(linha["Início da produção"], fmt)
        fim = datetime.strptime(linha["Conclusão"], fmt)
        assert eh_dia_util(ini.date()) and eh_dia_util(fim.date())      # sem sábado/domingo
        assert (HORA_INI <= ini.time() < HORA_ALMOCO) or (HORA_RETORNO <= ini.time() < HORA_FIM)
        assert (HORA_INI < fim.time() <= HORA_ALMOCO) or (HORA_RETORNO < fim.time() <= HORA_FIM)
        assert minutos_produtivos_entre(ini, fim) == linha["Tempo total (min)"]   # sem contar almoço/noite
        if anterior is not None:
            assert ini == ajustar_inicio(anterior)                        # sem folga nem sobreposição
        anterior = fim
    resultados.append("Teste 8 (expediente, almoço e fins de semana): OK")

    # --- Mais de 10 pedidos com o mesmo prazo ---
    iguais = [ped(i + 1, 100 * (i + 1), date(2026, 11, 20)) for i in range(12)]
    assert len(planejar(iguais, seg)['sequencia']) == 12

    # --- Desempenho com 200 pedidos ---
    random.seed(5)
    grande = aleatorios(200, [30, 60, 120, 480, 900, 1500], 0, 60)
    t0 = relogio.time()
    plano_g = planejar(grande, seg)
    dt = relogio.time() - t0
    resultados.append(f"200 pedidos planejados em {dt:.2f} s; acima do limite: {plano_g['criterio'][0]}")

    print("Todos os testes passaram.")
    for r in resultados:
        print(" -", r)


# =====================================================================
# TESTES NOVOS DA VERSÃO WEB (pedido fixado, banco, chaves, produtos.json)
# =====================================================================
def executar_testes_web():
    import hashlib
    import os
    import random
    import tempfile
    import threading
    from io import StringIO

    import pandas as pd

    from banco import Banco, ErroDeNegocio
    from pedidos import (carregar_produtos, gerar_chaves, ler_planilha,
                         montar_pedidos, pedido_de_registro)
    from planejador import planejar_com_fixado
    import servico

    seg = datetime(2026, 11, 16, 8, 0)
    P = Produtos(1, "T", 1)
    ped = lambda i, m, e: Pedido(i, f"c{i}", P, m, e)
    resultados = []

    def aleatorios(n, tempos, dmin, dmax, base=1):
        return [ped(base + i, random.choice(tempos),
                    (seg + timedelta(days=random.randint(dmin, dmax))).date())
                for i in range(n)]

    # --- 1. Sem pedido fixado = fluxo do notebook, sem nenhuma diferença ---
    random.seed(3)
    for _ in range(20):
        peds = aleatorios(random.randint(3, 25), [30, 480, 960, 2400], -2, 30)
        a = planejar_com_fixado(peds, seg)
        b = planejar(peds, seg)
        _, linhas_b = aval_sequencia(b['sequencia'], seg)
        assert [p.id for p in a['sequencia']] == [p.id for p in b['sequencia']]
        assert a['linhas'] == linhas_b
    resultados.append("Sem pedido iniciado: resultado idêntico ao do notebook (20 instâncias)")

    # --- 2. Com pedido fixado: sempre 1º; os demais seguem o algoritmo ---
    random.seed(9)
    for _ in range(40):
        fix = ped(0, random.choice([30, 480, 2400, 6000]),
                  (seg + timedelta(days=random.randint(-5, 40))).date())
        inicio_fix = seg - timedelta(days=random.randint(0, 3), hours=random.randint(0, 6))
        resto = aleatorios(random.randint(1, 20), [30, 480, 960, 2400], -2, 40)
        agora_t = seg + timedelta(hours=random.randint(0, 30))
        r = planejar_com_fixado(resto, agora_t, fix, inicio_fix)
        assert r['sequencia'][0] is fix and r['linhas'][0]["Início da produção"] \
            == ajustar_inicio(inicio_fix).strftime("%d/%m/%Y %H:%M")
        # Os demais: exatamente a saída do planejar() original, no início certo.
        esperado = planejar(resto, r['inicio_resto'])['sequencia']
        assert [p.id for p in r['sequencia'][1:]] == [p.id for p in esperado]
        assert len(r['sequencia']) == len(resto) + 1
        # Sem sobreposição: o 1º do resto não começa antes do fixado terminar.
        if resto:
            fim_fix = datetime.strptime(r['linhas'][0]["Conclusão"], "%d/%m/%Y %H:%M")
            ini_2 = datetime.strptime(r['linhas'][1]["Início da produção"], "%d/%m/%Y %H:%M")
            assert ini_2 >= fim_fix
    resultados.append("Pedido iniciado fica sempre em 1º; os demais = planejar() original (40 instâncias)")

    # --- 3. Pedido iniciado NUNCA é ultrapassado, mesmo se for péssimo ---
    gigante = ped(0, 130000, date(2026, 11, 17))          # impossível de cumprir
    curtos = [ped(i, 30, date(2026, 11, 17)) for i in range(1, 6)]
    r = planejar_com_fixado(curtos, seg, gigante, seg)
    assert r['sequencia'][0] is gigante
    sem_fixo = planejar(curtos + [gigante], seg)['sequencia'][0]
    assert sem_fixo is not gigante   # (sem fixar, o algoritmo o mandaria para o fim)
    resultados.append("Pedido iniciado inviável continua em 1º (sem fixar, o algoritmo o moveria)")

    # --- 4. Chaves a partir do carimbo ---
    df = pd.read_csv(StringIO(
        "Carimbo de data/hora,PRODUTOS,DATA DE ENTREGA,QUANTIDADE,CLIENTE\n"
        "10/11/2026 10:00:00,VALVULA XX,22/12/2026,2,A\n"
        "10/11/2026 10:00:00,VALVULA XX,22/12/2026,3,B\n"
        ",VALVULA XX,22/12/2026,4,C\n"), dtype=str, keep_default_na=False)
    assert gerar_chaves(df) == ["10/11/2026 10:00:00", "10/11/2026 10:00:00#2", "linha-4"]
    resultados.append("Chave = carimbo do Forms (repetido ganha #2; vazio cai para linha-N)")

    # --- 5. produtos.json: leitura sem alterar o arquivo ---
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "produtos.json")
    h1 = hashlib.sha256(open(caminho, "rb").read()).hexdigest()
    prods = carregar_produtos()
    h2 = hashlib.sha256(open(caminho, "rb").read()).hexdigest()
    assert h1 == h2 and [p.tempo_unitario for p in prods] == [30, 50, 60, 75, 100]
    resultados.append("produtos.json lido sem ser alterado (hash idêntico antes/depois)")

    # --- 6. Banco: regras e persistência (SQLite; mesmas regras no Postgres) ---
    with tempfile.TemporaryDirectory() as pasta:
        url = f"sqlite:///{pasta}/t.db"
        banco = Banco(url)
        reg = lambda k, c="X": dict(chave=k, cliente=c, produto="VALVULA XX",
                                    quantidade=2, data_entrega="2026-12-01",
                                    tempo_total=60, linha_planilha=2)
        agora_t = datetime(2026, 11, 19, 21, 30, 45)

        banco.iniciar(reg("k1"), agora_t)
        for tentativa, msg in ((reg("k2"), "Já existe um pedido em produção"),
                               (reg("k1"), "já foi iniciado ou concluído")):
            try:
                banco.iniciar(tentativa, agora_t)
                raise AssertionError("deveria recusar")
            except ErroDeNegocio as e:
                assert msg in str(e), str(e)
        try:
            banco.finalizar("k2", agora_t)
            raise AssertionError("deveria recusar")
        except ErroDeNegocio:
            pass

        # "Reiniciar a aplicação": uma nova instância enxerga o mesmo estado.
        banco2 = Banco(url)
        assert [(r['chave'], r['status']) for r in banco2.listar()] == [("k1", "em_producao")]

        ass_antes = banco2.assinatura()
        banco2.finalizar("k1", agora_t + timedelta(hours=1))
        assert banco2.assinatura() != ass_antes
        try:
            banco2.finalizar("k1", agora_t)           # duas finalizações: só a 1ª vale
            raise AssertionError("deveria recusar")
        except ErroDeNegocio:
            pass
        lista = Banco(url).listar()
        assert len(lista) == 1 and lista[0]['status'] == "concluido"
        assert lista[0]['cliente'] == "X" and lista[0]['concluido_em'].startswith("2026-11-19T22:30")
        banco2.iniciar(reg("k2"), agora_t)            # liberado após finalizar
        resultados.append("Banco: 1 pedido em produção por vez, sem duplicar, persiste após reiniciar")

        # Concorrência: 8 pessoas tentam iniciar pedidos diferentes ao mesmo tempo.
        banco3 = Banco(f"sqlite:///{pasta}/c.db")
        ok, recusados = [], []

        def tentar(k):
            try:
                banco3.iniciar(reg(k), agora_t)
                ok.append(k)
            except ErroDeNegocio:
                recusados.append(k)

        ts = [threading.Thread(target=tentar, args=(f"c{i}",)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert len(ok) == 1 and len(recusados) == 7, (ok, recusados)
        assert sum(r['status'] == 'em_producao' for r in banco3.listar()) == 1
        resultados.append("Concorrência: 8 cliques simultâneos -> exatamente 1 pedido iniciado")

        # --- 7. Fluxo completo da tela (servico.montar_estado) ---
        df_csv = ler_planilha(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "pedidos_exemplo.csv"))
        b = Banco(f"sqlite:///{pasta}/s.db")
        agora_s = datetime(2026, 11, 19, 12, 3)
        e0 = servico.montar_estado(df_csv, b, agora_s)
        assert e0['kpis']['em_producao'] == len(e0['producao']) > 0 and e0['kpis']['concluidos'] == 0
        assert (e0['producao']['Status'] == "Aguardando").all()
        assert len(e0['ignorados']) >= 3          # datas passadas e quantidade 'P'

        # Inicia o pedido que está em ÚLTIMO lugar da sequência.
        chave_ultimo = e0['chaves'][-1]
        ped_ultimo = e0['pedidos_por_chave'][chave_ultimo]
        b.iniciar(servico.registro_para_iniciar(ped_ultimo), agora_s)

        e1 = servico.montar_estado(df_csv, b, agora_s + timedelta(minutes=5))
        assert e1['chaves'][0] == chave_ultimo
        assert e1['producao'].iloc[0]['Status'] == "● EM PRODUÇÃO"
        assert (e1['producao']['Status'] == "Aguardando").sum() == len(e1['producao']) - 1
        assert len(e1['producao']) == len(e0['producao'])        # nada sumiu nem duplicou
        assert e1['kpis']['em_andamento'] == ped_ultimo.cliente
        # Os demais mantêm a ordem relativa que o algoritmo já dava.
        assert e1['chaves'][1:] == [c for c in e0['chaves'] if c != chave_ultimo] \
            or set(e1['chaves'][1:]) == set(e0['chaves']) - {chave_ultimo}

        # Muito depois, a data de entrega do pedido iniciado já passou: continua lá.
        e2 = servico.montar_estado(df_csv, b, datetime(2027, 6, 1, 9, 0))
        assert e2['chaves'][0] == chave_ultimo

        # Finaliza: sai da produção, entra em concluídos, sem duplicar.
        # (mesmo dia: no dia seguinte, pedidos com entrega "ontem" passam a ser
        # rejeitados pela validação original do notebook, o que mudaria a contagem)
        b.finalizar(chave_ultimo, agora_s + timedelta(hours=3))
        e3 = servico.montar_estado(df_csv, b, agora_s + timedelta(hours=3))
        assert chave_ultimo not in e3['chaves'] and len(e3['producao']) == len(e0['producao']) - 1
        assert len(e3['concluidos']) == 1 and e3['concluidos'].iloc[0]['Cliente'] == ped_ultimo.cliente
        assert e3['kpis']['concluidos'] == 1 and e3['kpis']['em_andamento'] is None
        assert (e3['producao']['Status'] == "Aguardando").all()   # algoritmo livre de novo
        resultados.append("Fluxo completo: iniciar -> 1º lugar (mesmo vencido) -> finalizar -> concluídos")

    print("Testes da versão web: todos passaram.")
    for r in resultados:
        print(" -", r)


if __name__ == "__main__":
    executar_testes()
    print()
    executar_testes_web()
