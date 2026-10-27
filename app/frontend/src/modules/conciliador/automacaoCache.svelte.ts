// Cache reativo que persiste entre montagens do AutomacaoModal.
// Por ser um modulo .svelte.ts, o $state sobrevive ao ciclo de vida do componente.

export interface CaixaItem {
  data: string;
  pdv: string;
  turno: string;
  movto: string;
  status: string;
  horario_abertura?: string;
  horario_fechamento: string;
  valor?: string;
  row_index: number;
}

export interface CaixaIdent {
  data: string;
  pdv: string;
  turno: string;
  movto: string;
  row_index?: number;
}

export interface AutomacaoStatus {
  state: "off" | "warming" | "ready" | "headed" | "error" | string;
  detail: string;
  headed: boolean;
  browser_aberto: boolean;
  ocupado: boolean;
  timings_ms: Record<string, number>;
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
      const err = await res.json().catch(() => ({}));
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

export async function fetchStatus(): Promise<AutomacaoStatus | null> {
  try {
    const res = await fetch("/api/conciliador/automacao/status");
    if (!res.ok) return null;
    return (await res.json()) as AutomacaoStatus;
  } catch {
    return null;
  }
}

export async function reconectarAutomacao(): Promise<string | null> {
  try {
    const res = await fetch("/api/conciliador/automacao/reconectar", { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return err.detail || "Falha ao reconectar a automacao.";
    }
    return null;
  } catch (e: any) {
    return e.message || "Erro de conexao.";
  }
}

export async function fecharNavegadorAutomacao(): Promise<string | null> {
  try {
    const res = await fetch("/api/conciliador/automacao/navegador/fechar", { method: "POST" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return err.detail || "Falha ao fechar o navegador.";
    }
    return null;
  } catch (e: any) {
    return e.message || "Erro de conexao.";
  }
}

/** dd/mm/yyyy (Cloudfy) -> yyyy-mm-dd (campo data do caixa). */
export function normalizeDate(raw: string): string {
  const text = String(raw || "").trim();
  const br = text.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (br) return `${br[3]}-${br[2]}-${br[1]}`;
  const br2 = text.match(/^(\d{2})\/(\d{2})\/(\d{2})/);
  if (br2) return `20${br2[3]}-${br2[2]}-${br2[1]}`;
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(0, 10) : text;
}

/** Chave estável usada pela API em vez do índice da linha. */
export function caixaChave(caixa: CaixaItem): CaixaIdent {
  return {
    data: String(caixa.data || "").trim(),
    pdv: String(caixa.pdv || "").trim(),
    turno: String(caixa.turno || "").trim(),
    movto: String(caixa.movto || "").trim(),
    row_index: caixa.row_index,
  };
}

/** Turno do caixa pela coluna Turno; fallback ao texto de Movto (T1/T2). */
export function turnoCaixa(caixa: CaixaItem): number | null {
  const digits = String(caixa.turno || "").replace(/\D/g, "");
  if (digits === "1" || digits === "2") return Number(digits);
  const movto = String(caixa.movto || "").match(/\bT\s*([12])\b/i);
  return movto ? Number(movto[1]) : null;
}

export function mesmaDataCaixa(raw: string, isoDate: string): boolean {
  if (!isoDate) return true;
  return normalizeDate(raw) === isoDate;
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
