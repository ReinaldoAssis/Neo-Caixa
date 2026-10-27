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

/** dd/mm/yyyy (Cloudfy) -> yyyy-mm-dd (campo data do caixa). */
function normalizeDate(raw: string): string {
  const text = String(raw || "").trim();
  const br = text.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (br) return `${br[3]}-${br[2]}-${br[1]}`;
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(0, 10) : text;
}

/** Hora de fechamento do turno 1 para a data (formato "dd/mm HH:MM"). */
export function turno1Fechamento(
  isoDate: string,
): { hora: string; pdv: string; movto: string } | null {
  for (const caixa of _caixas) {
    if (normalizeDate(caixa.data) !== isoDate) continue;

    const turno = String(caixa.turno || "").replace(/\D/g, "");
    const movtoT1 = /\bT\s*1\b/i.test(String(caixa.movto || ""));
    if (turno !== "1" && !movtoT1) continue;

    const match = String(caixa.horario_fechamento || "").match(/(\d{2}):(\d{2})\s*$/);
    if (!match) continue;

    const hora = `${match[1]}:${match[2]}`;
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(hora)) continue;

    return { hora, pdv: caixa.pdv || "", movto: caixa.movto || "" };
  }
  return null;
}
