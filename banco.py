"""
banco.py - Persistência compartilhada (status "em produção" / "concluído").

Produção: Postgres do Supabase (URL "postgresql://...").
Desenvolvimento/testes locais: SQLite ("sqlite:///arquivo.db"), mesma lógica.

Garantias (aplicadas pelo próprio banco, então valem mesmo com vários
visitantes clicando ao mesmo tempo):
  * Um pedido só pode ser iniciado uma vez (chave primária).
  * Só pode existir UM pedido em produção (índice único parcial).
  * Finalizar é um UPDATE condicional: só funciona se o pedido ainda estiver
    "em_producao", então não há duplicação nem perda de dados.
  * O instantâneo do pedido (cliente, produto, quantidade, entrega, tempo) é
    gravado ao iniciar e preservado ao concluir, mesmo que a linha mude ou
    saia da planilha.
"""
import sqlite3
from contextlib import contextmanager

COLUNAS = ('chave', 'status', 'cliente', 'produto', 'quantidade',
           'data_entrega', 'tempo_total', 'linha_planilha',
           'iniciado_em', 'concluido_em')

DDL_TABELA = """
CREATE TABLE IF NOT EXISTS pedidos_estado (
    chave          TEXT PRIMARY KEY,
    status         TEXT NOT NULL CHECK (status IN ('em_producao', 'concluido')),
    cliente        TEXT NOT NULL,
    produto        TEXT NOT NULL,
    quantidade     INTEGER NOT NULL,
    data_entrega   TEXT NOT NULL,
    tempo_total    INTEGER NOT NULL,
    linha_planilha INTEGER,
    iniciado_em    TEXT NOT NULL,
    concluido_em   TEXT
)
"""

# Todas as linhas "em_producao" têm status igual, então este índice único
# parcial impede dois pedidos em produção ao mesmo tempo.
DDL_INDICE = """
CREATE UNIQUE INDEX IF NOT EXISTS um_pedido_em_producao
    ON pedidos_estado (status) WHERE status = 'em_producao'
"""

# Supabase expõe tabelas do schema public pela API REST. Com RLS ligada e sem
# nenhuma política, a API pública não enxerga nada; a conexão direta usada
# por este app (usuário postgres) continua funcionando.
DDL_RLS = "ALTER TABLE pedidos_estado ENABLE ROW LEVEL SECURITY"

FORMATO_TS = "%Y-%m-%dT%H:%M:%S"


class ErroDeNegocio(Exception):
    """Ação recusada por regra do sistema (mensagem pronta para o usuário)."""


class Banco:
    def __init__(self, url):
        self.url = url
        self.postgres = url.startswith(("postgres://", "postgresql://"))
        if not self.postgres:
            self.caminho = url.replace("sqlite:///", "", 1)
        self._preparar()

    # ------------------------------------------------------------ infra
    @property
    def nome(self):
        return "Supabase (Postgres)" if self.postgres else "SQLite local"

    def _sql(self, sql):
        return sql if self.postgres else sql.replace("%s", "?")

    @contextmanager
    def _transacao(self):
        """Uma transação: confirma ao sair, desfaz se houver erro."""
        if self.postgres:
            import psycopg
            # prepare_threshold=None: compatível com o pooler do Supabase.
            with psycopg.connect(self.url, prepare_threshold=None,
                                 connect_timeout=15) as conn:
                with conn.cursor() as cur:
                    yield cur
        else:
            conn = sqlite3.connect(self.caminho, timeout=15)
            try:
                cur = conn.cursor()
                yield cur
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _preparar(self):
        with self._transacao() as cur:
            cur.execute(DDL_TABELA)
            cur.execute(DDL_INDICE)
            if self.postgres:
                cur.execute(DDL_RLS)

    @staticmethod
    def _violacao_unica(erro):
        if isinstance(erro, sqlite3.IntegrityError):
            return True
        return getattr(erro, "sqlstate", None) == "23505"

    # ---------------------------------------------------------- leitura
    def listar(self):
        """Todos os registros (em produção e concluídos), como dicts."""
        with self._transacao() as cur:
            cur.execute(f"SELECT {', '.join(COLUNAS)} FROM pedidos_estado "
                        "ORDER BY iniciado_em, chave")
            return [dict(zip(COLUNAS, linha)) for linha in cur.fetchall()]

    def assinatura(self):
        """Valor que muda sempre que algo é iniciado ou finalizado."""
        with self._transacao() as cur:
            cur.execute("SELECT COUNT(*), COALESCE(MAX(iniciado_em), ''), "
                        "COALESCE(MAX(concluido_em), '') FROM pedidos_estado")
            return tuple(str(v) for v in cur.fetchone())

    # ----------------------------------------------------------- escrita
    def iniciar(self, registro, agora):
        """Marca o pedido como em produção (grava o instantâneo dele)."""
        valores = (
            registro['chave'], 'em_producao', registro['cliente'],
            registro['produto'], int(registro['quantidade']),
            registro['data_entrega'], int(registro['tempo_total']),
            registro.get('linha_planilha'), agora.strftime(FORMATO_TS),
        )
        try:
            with self._transacao() as cur:
                cur.execute(self._sql(
                    "INSERT INTO pedidos_estado (chave, status, cliente, "
                    "produto, quantidade, data_entrega, tempo_total, "
                    "linha_planilha, iniciado_em) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (chave) DO NOTHING"), valores)
                if cur.rowcount != 1:
                    raise ErroDeNegocio(
                        "Este pedido já foi iniciado ou concluído "
                        "(talvez por outra pessoa). Atualize a página.")
        except ErroDeNegocio:
            raise
        except Exception as erro:
            if self._violacao_unica(erro):
                raise ErroDeNegocio(
                    "Já existe um pedido em produção. Finalize-o antes de "
                    "iniciar outro.") from erro
            raise

    def finalizar(self, chave, agora):
        """Move o pedido em produção para concluídos."""
        with self._transacao() as cur:
            cur.execute(self._sql(
                "UPDATE pedidos_estado SET status = 'concluido', "
                "concluido_em = %s WHERE chave = %s AND status = 'em_producao'"),
                (agora.strftime(FORMATO_TS), chave))
            if cur.rowcount != 1:
                raise ErroDeNegocio(
                    "Este pedido não está em produção (talvez já tenha sido "
                    "finalizado por outra pessoa). Atualize a página.")
