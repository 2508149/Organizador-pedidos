"""
pedidos.py - Classes, validação e leitura dos pedidos.

Os blocos "Classes" e "Validação" são CÓPIAS LITERAIS das células 4 e 6 do
notebook. As funções de leitura (produtos.json somente leitura e planilha CSV)
estão na seção final, marcada como adaptação para a versão web.
"""
import json
import re
from datetime import datetime, date
from pathlib import Path

import pandas as pd


# =====================================================================
# 4. Classes (notebook, célula 4)
# =====================================================================
# classe responsavel pelos produtos
class Produtos:
    def __init__(self, id, nome, tempo_unitario):
        self.id = id
        self.nome = nome
        self.tempo_unitario = tempo_unitario
        # essa é a parte por amazenar as informações dentro dos objetos objeto
        # nesse caso

# class: essa é a funçaõ que cria um classe (nesse caso produto)
# def__init__(): é o metodo que constroi e executa quando criamos um objeto para essa classe
# self: é oq vai representa o objeto que esta sendo criado
# id, nome, tempo_unitario: as informações para criarmos o produto

# classe responsavel pelos pedidos
class Pedido:
    def __init__(self, id, cliente, produto, quantidade, data_entrega):
        self.id = id
        self.cliente = cliente
        self.produto = produto              # objeto da classe Produtos
        self.quantidade = quantidade
        self.data_entrega = data_entrega    # objeto datetime.date
        self.tempo_total = produto.tempo_unitario * quantidade # calcula o tempo de produção


# classe responsavel por gerenciar os pedidos
class GerenPeds:
    def __init__(self):
    # es
        self.lista_peds = []

    def adici_ped(self, cliente, produto, quantidade, data_entrega):
        novo_id = len(self.lista_peds) + 1
        novo_ped = Pedido(novo_id, cliente, produto, quantidade, data_entrega)
        self.lista_peds.append(novo_ped)


# =====================================================================
# 6. Validação dos dados (notebook, célula 6)
# =====================================================================
def normalizar_texto(texto):
    # Remove espaços extras e ignora maiúsculas/minúsculas.
    return " ".join(str(texto).split()).upper()


def validar_quantidade(valor):
    # Retorna (quantidade_int, None) se válida ou (None, mensagem_de_erro).
    if isinstance(valor, bool):
        return None, f"Quantidade inválida: '{valor}'"
    if isinstance(valor, int):
        quantidade = valor
    elif isinstance(valor, float):
        if not valor.is_integer():
            return None, f"Quantidade decimal não permitida: '{valor}'"
        quantidade = int(valor)
    else:
        texto = str(valor).strip()
        if texto == "":
            return None, "Quantidade vazia"
        if re.fullmatch(r"[+-]?\d+", texto):
            quantidade = int(texto)
        elif re.fullmatch(r"[+-]?\d+[.,]\d+", texto):
            return None, f"Quantidade decimal não permitida: '{texto}'"
        else:
            return None, f"Quantidade não numérica: '{texto}'"
    if quantidade <= 0:
        return None, f"Quantidade deve ser positiva: '{quantidade}'"
    return quantidade, None


def converter_data(valor):
    # Retorna (date, None) se a data existe ou (None, mensagem_de_erro).
    if isinstance(valor, datetime):
        return valor.date(), None
    if isinstance(valor, date):
        return valor, None
    texto = str(valor).strip()
    if texto == "":
        return None, "Data de entrega vazia"
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date(), None
        except ValueError:
            pass
    return None, f"Data de entrega inválida ou inexistente: '{texto}'"


def validar_pedido(linha, mapa_produtos, hoje):
    # Valida uma linha (dict). Retorna (dados_ou_None, lista_de_erros).
    erros = []

    cliente = str(linha.get('CLIENTE', '')).strip()
    if cliente == "":
        erros.append("Cliente vazio")

    nome_produto = str(linha.get('PRODUTOS', '')).strip()
    produto = None
    if nome_produto == "":
        erros.append("Produto vazio")
    else:
        produto = mapa_produtos.get(normalizar_texto(nome_produto))
        if produto is None:
            erros.append(f"Produto não cadastrado: '{nome_produto}'")

    quantidade, erro = validar_quantidade(linha.get('QUANTIDADE', ''))
    if erro:
        erros.append(erro)

    data_entrega, erro = converter_data(linha.get('DATA DE ENTREGA', ''))
    if erro:
        erros.append(erro)
    elif data_entrega < hoje:
        erros.append(
            f"Data de entrega anterior a hoje: {data_entrega.strftime('%d/%m/%Y')}"
        )

    if erros:
        return None, erros
    return {
        'cliente': cliente,
        'produto': produto,
        'quantidade': quantidade,
        'data_entrega': data_entrega,
    }, []


# =====================================================================
# ADAPTAÇÕES PARA A VERSÃO WEB (NÃO existem no notebook)
# =====================================================================
CAMINHO_PRODUTOS = Path(__file__).with_name("produtos.json")
COLUNA_CARIMBO = "Carimbo de data/hora"
COLUNAS_OBRIGATORIAS = ['PRODUTOS', 'DATA DE ENTREGA', 'QUANTIDADE', 'CLIENTE']


def carregar_produtos(caminho=CAMINHO_PRODUTOS):
    """Lê o produtos.json (SOMENTE LEITURA) e devolve a lista de Produtos.

    Mesma validação do notebook: tempo_unitario deve ser positivo.
    """
    with open(caminho, 'r', encoding='utf-8') as arquivo:
        dados_prod = json.load(arquivo)

    lista_prods = []
    for item_prod in dados_prod['produtos']:
        if item_prod['tempo_unitario'] <= 0:
            raise ValueError(
                f"Produto '{item_prod['nome']}' com tempo unitário inválido "
                f"({item_prod['tempo_unitario']}). Corrija o produtos.json."
            )
        lista_prods.append(Produtos(
            item_prod['id'], item_prod['nome'], item_prod['tempo_unitario']
        ))
    return lista_prods


def ler_planilha(origem):
    """Lê os pedidos de um CSV (URL publicada do Google Sheets ou arquivo).

    Equivale a pd.DataFrame(aba.get_all_records()) do notebook, mas lendo
    tudo como texto (a validação converte e rejeita valores inválidos).
    """
    df = pd.read_csv(origem, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise KeyError(f"Colunas ausentes na planilha: {faltando}")
    # Ignora linhas totalmente vazias SEM renumerar o índice, para que
    # 'Linha na planilha' (indice + 2) continue correto.
    return df[(df != "").any(axis=1)]


def gerar_chaves(df):
    """Identificador persistente de cada linha: o carimbo de data/hora do Forms.

    - Carimbo repetido (dois envios no mesmo segundo) recebe sufixo #2, #3...
    - Carimbo ausente ou vazio cai para 'linha-N' (último recurso).
    """
    vistos, chaves = {}, []
    tem_carimbo = COLUNA_CARIMBO in df.columns
    for indice in df.index:
        base = str(df.at[indice, COLUNA_CARIMBO]).strip() if tem_carimbo else ""
        if base == "":
            base = f"linha-{indice + 2}"
        vistos[base] = vistos.get(base, 0) + 1
        chaves.append(base if vistos[base] == 1 else f"{base}#{vistos[base]}")
    return chaves


def montar_pedidos(df, mapa_produtos, hoje, chaves_ignorar=()):
    """Equivale à seção 6 do notebook (valida e monta os Pedidos).

    Linhas cuja chave está em `chaves_ignorar` (pedidos já iniciados ou
    concluídos, guardados no banco) são puladas: elas não passam pela
    validação, pois a data de entrega delas pode já ter passado.
    Retorna (gerenciador, pedidos_ignorados).
    """
    gerenciador = GerenPeds()
    pedidos_ignorados = []

    for (indice, linha), chave in zip(df.iterrows(), gerar_chaves(df)):
        if chave in chaves_ignorar:
            continue
        dados, erros = validar_pedido(linha.to_dict(), mapa_produtos, hoje)
        if erros:
            pedidos_ignorados.append({
                'Linha na planilha': indice + 2,
                'Cliente': linha.get('CLIENTE', ''),
                'Motivos': "; ".join(erros),
            })
            continue
        gerenciador.adici_ped(
            dados['cliente'], dados['produto'],
            dados['quantidade'], dados['data_entrega']
        )
        # Guarda a chave persistente ao lado do id (o id do algoritmo
        # continua sendo sequencial, como no notebook).
        gerenciador.lista_peds[-1].chave = chave
        gerenciador.lista_peds[-1].linha = indice + 2

    return gerenciador, pedidos_ignorados


def pedido_de_registro(registro, mapa_produtos, id_pedido=0):
    """Reconstrói um Pedido a partir do instantâneo salvo no banco."""
    produto = mapa_produtos.get(normalizar_texto(registro['produto']))
    if produto is None:   # produto removido do JSON depois do início
        produto = Produtos(
            0, registro['produto'],
            registro['tempo_total'] / registro['quantidade']
        )
    ped = Pedido(id_pedido, registro['cliente'], produto,
                 registro['quantidade'],
                 date.fromisoformat(registro['data_entrega']))
    ped.chave = registro['chave']
    ped.linha = registro.get('linha_planilha')
    return ped
