// Cache reativo que persiste entre montagens do AutomacaoModal.
// Por ser um modulo .svelte.ts, o $state sobrevive ao ciclo de vida do componente.

interface CaixaItem {
  data: string;
  pdv: string;
  turno: string;
  movto: string;
  status: string;
  horario_fechamento: string;
  row_index: number;
}

let _caixas: CaixaItem[] = $state([]);
let _fetched = $state(false);
let _loading = $state(false);
let _error = $state("");

export function getCaixas() {
  return _caixas;
}

export function isFetched() {
  return _fetched;
}

export function isLoading() {
  return _loading;
}

export function getError() {
  return _error;
}

export function clearError() {
  _error = "";
}

export async function fetchCaixas() {
  _loading = true;
  _error = "";
  try {
    const res = await fetch("/api/conciliador/automacao/listar", {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json();
      _error = err.detail || "Erro ao listar caixas.";
      _loading = false;
      return;
    }
    const data = await res.json();
    _caixas = data.caixas || [];
    _fetched = true;
    if (_caixas.length === 0) {
      _error = "Nenhum caixa pendente encontrado.";
    }
  } catch (e: any) {
    _error = e.message || "Erro de conexao.";
  } finally {
    _loading = false;
  }
}
