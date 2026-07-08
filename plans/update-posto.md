
Quero que se baseie no seguinte código de um app passado para fazer as devidas atualizações no código do caixa posto atual

import React, { useState, useEffect, useRef } from "react";
import { base44 } from "@/api/base44Client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Save, Loader2, Printer, Pencil, Trash2, ChevronDown, ChevronUp, PlusCircle, Upload } from "lucide-react";
import { processImportedRows, parseCSVText, PAYMENT_RULES, processPagBankCSV, processPremmiaRows, PAGBANK_KEYS } from "@/lib/caixaImport";
import { formatCurrency } from "@/lib/currency";
import TableNumberInput from "@/components/TableNumberInput";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger
} from "@/components/ui/alert-dialog";

// === Tabela Principal (parte superior) ===
// Exatamente as linhas conforme a imagem
const ROWS = [
  { key: "premmia_cartao", label: "PREMMIA CARTÃO" },
  { key: "premmia_pix",    label: "PREMMIA PIX" },
  { key: "premmia_vale",   label: "PREMMIA VALE" },
  { key: "premmia_cupom",  label: "PREMMIA CUPOM" },
  { key: "cartao_fitcard", label: "CARTÃO FITCARD" },
  { key: "pag_pix",        label: "PAG PIX" },
  { key: "american_exp",   label: "AMERICAN EXP" },
  { key: "elo_credito",    label: "ELO CRÉDITO" },
  { key: "elo_debito",     label: "ELO DÉBITO" },
  { key: "mastercard_c",   label: "MASTERCARD C" },
  { key: "mastercard_d",   label: "MASTERCARD D" },
  { key: "visa_credito",   label: "VISA CRÉDITO" },
  { key: "visa_debito",    label: "VISA DÉBITO" },
];

// Mapeamento: coluna da tabela inferior → linha PREMMIA da tabela superior (campo _site)
const DETALHE_COLS = [
  { key: "cartao", label: "CARTÃO",  premmiaKey: "premmia_cartao" },
  { key: "pix",    label: "PIX",     premmiaKey: "premmia_pix" },
  { key: "vale",   label: "VALE",    premmiaKey: "premmia_vale" },
  { key: "cupom",  label: "CUPOM",   premmiaKey: "premmia_cupom" },
];

const NUM_DETALHE_ROWS = 8; // linhas em branco para lançamento na tabela inferior

const emptyDetalhe = () =>
  Array.from({ length: NUM_DETALHE_ROWS }, () => ({
    cartao: "", pix: "", vale: "", cupom: "",
  }));

const emptyTable = () => {
  const obj = {};
  ROWS.forEach((r) => {
    obj[`${r.key}_sistema`] = "";
    obj[`${r.key}_site`] = "";
    obj[`${r.key}_pix`] = "";
  });
  return obj;
};

const colSum = (data, col) =>
  ROWS.reduce((s, r) => s + (Number(data[`${r.key}_${col}`]) || 0), 0);

const detalheColSum = (rows, col) =>
  rows.reduce((s, r) => s + (Number(r[col]) || 0), 0);

export default function Caixas() {
  const [companies, setCompanies] = useState([]);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [printRecord, setPrintRecord] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importType, setImportType] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [importErr, setImportErr] = useState("");
  const fileInputRef = useRef(null);
  const pagBankFileRef = useRef(null);
  const premmiaFileRef = useRef(null);

  const [header, setHeader] = useState({
    company_id: "", date: new Date().toISOString().split("T")[0], shift: "", notes: "",
  });
  const [tableData, setTableData] = useState(emptyTable());
  const [detalheRows, setDetalheRows] = useState(emptyDetalhe());

  const [filterCompany, setFilterCompany] = useState("all");
  const [filterDate, setFilterDate] = useState("");

  useEffect(() => { loadCompanies(); loadRecords(); }, []);

  const loadCompanies = async () => {
    const data = await base44.entities.Company.filter({ status: "Ativa" });
    setCompanies(data);
  };

  const loadRecords = async () => {
    setLoading(true);
    const data = await base44.entities.CaixaConferencia.list("-date", 100);
    setRecords(data);
    setLoading(false);
  };

  const resetForm = () => {
    setHeader({ company_id: "", date: new Date().toISOString().split("T")[0], shift: "", notes: "" });
    setTableData(emptyTable());
    setDetalheRows(emptyDetalhe());
    setEditingId(null);
  };

  // Calcula os totais da tabela inferior e injeta no campo _site das premmias
  const computeTableWithDetalhe = (td, rows) => {
    const result = { ...td };
    DETALHE_COLS.forEach((dc) => {
      const total = detalheColSum(rows, dc.key);
      result[`${dc.premmiaKey}_site`] = total > 0 ? total : td[`${dc.premmiaKey}_site`];
    });
    return result;
  };

  const setCell = (key, val) => setTableData((prev) => {
    const next = { ...prev, [key]: val };
    if (key.endsWith("_pix")) {
      next.pag_pix_site = ROWS.reduce((s, r) => s + (Number(next[`${r.key}_pix`]) || 0), 0);
    }
    return next;
  });

  const setDetalheCell = (rowIdx, col, val) => {
    setDetalheRows((prev) => {
      const next = prev.map((r, i) => i === rowIdx ? { ...r, [col]: val } : r);
      // Auto-inject totals into table
      setTableData((td) => {
        const result = { ...td };
        DETALHE_COLS.forEach((dc) => {
          const total = detalheColSum(next, dc.key);
          if (total > 0) result[`${dc.premmiaKey}_site`] = total;
        });
        return result;
      });
      return next;
    });
  };

  const addDetalheRow = () =>
    setDetalheRows((prev) => [...prev, { cartao: "", pix: "", vale: "", cupom: "" }]);

  const handleEdit = (record) => {
    setHeader({
      company_id: record.company_id || "",
      date: record.date || "",
      shift: record.shift || "",
      notes: record.notes || "",
    });
    const td = {};
    ROWS.forEach((r) => {
      td[`${r.key}_sistema`] = record[`${r.key}_sistema`] ?? "";
      td[`${r.key}_site`]    = record[`${r.key}_site`] ?? "";
      td[`${r.key}_pix`]     = record[`${r.key}_pix`] ?? "";
    });
    setTableData(td);
    // Restore detalhe rows
    try {
      const cartao = JSON.parse(record.detalhe_cartao || "[]");
      const pix    = JSON.parse(record.detalhe_pix    || "[]");
      const vale   = JSON.parse(record.detalhe_vale   || "[]");
      const cupom  = JSON.parse(record.detalhe_cupom  || "[]");
      const len = Math.max(cartao.length, pix.length, vale.length, cupom.length, NUM_DETALHE_ROWS);
      const rows = Array.from({ length: len }, (_, i) => ({
        cartao: cartao[i] ?? "",
        pix:    pix[i]    ?? "",
        vale:   vale[i]   ?? "",
        cupom:  cupom[i]  ?? "",
      }));
      setDetalheRows(rows);
    } catch { setDetalheRows(emptyDetalhe()); }
    setEditingId(record.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id) => {
    await base44.entities.CaixaConferencia.delete(id);
    await loadRecords();
  };

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!header.company_id || !header.date) {
      setImportErr("Selecione a empresa e a data antes de importar.");
      e.target.value = "";
      return;
    }
    setImporting(true);
    setImportType("caixa");
    setImportErr("");
    setImportMsg("");
    try {
      let rows;
      const isCSV = file.name.toLowerCase().endsWith(".csv");

      if (isCSV) {
        const text = await file.text();
        rows = parseCSVText(text);
      } else {
        const { file_url } = await base44.integrations.Core.UploadFile({ file });
        const result = await base44.integrations.Core.ExtractDataFromUploadedFile({
          file_url,
          json_schema: {
            type: "object",
            properties: {
              rows: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    descricao: { type: "string" },
                    valor: { type: "number" },
                  },
                },
              },
            },
          },
        });
        const extracted = Array.isArray(result.output) ? result.output : result.output?.rows || [];
        rows = extracted.map((r) => [r.descricao ?? "", r.valor ?? ""]);
      }

      const { values, processedCount, notFound } = processImportedRows(rows);

      // Fill _sistema fields for display
      const newTable = { ...tableData };
      PAYMENT_RULES.forEach((rule) => {
        newTable[`${rule.key}_sistema`] = values[rule.key];
      });
      setTableData(newTable);

      // Check for existing record same company + date
      let existingId = editingId;
      let existingRecord = null;
      if (existingId) {
        existingRecord = records.find((r) => r.id === existingId) || null;
      } else {
        const existing = await base44.entities.CaixaConferencia.filter({
          company_id: header.company_id,
          date: header.date,
        });
        if (existing.length > 0) {
          existingId = existing[0].id;
          existingRecord = existing[0];
          setEditingId(existingId);
        }
      }

      const company = companies.find((c) => c.id === header.company_id);
      const now = new Date();
      const timestamp = now.toLocaleString("pt-BR");
      const importInfo = `[Importado em ${timestamp} — ${processedCount} registro(s) processado(s)]`;
      const notFoundInfo = notFound.length > 0
        ? `\nFormas não encontradas: ${notFound.join(", ")}`
        : "";
      const userNote = header.notes || "";
      const finalNotes = `${importInfo}${notFoundInfo}${userNote ? "\n" + userNote : ""}`;

      const payload = {
        company_id: header.company_id,
        company_name: company?.name || "",
        date: header.date,
        shift: header.shift || "",
        notes: finalNotes,
        detalhe_cartao: JSON.stringify(detalheRows.map((r) => r.cartao)),
        detalhe_pix: JSON.stringify(detalheRows.map((r) => r.pix)),
        detalhe_vale: JSON.stringify(detalheRows.map((r) => r.vale)),
        detalhe_cupom: JSON.stringify(detalheRows.map((r) => r.cupom)),
      };
      PAYMENT_RULES.forEach((rule) => {
        payload[`${rule.key}_sistema`] = values[rule.key];
        payload[`${rule.key}_site`] = existingRecord?.[`${rule.key}_site`] ?? (Number(tableData[`${rule.key}_site`]) || 0);
        payload[`${rule.key}_pix`] = existingRecord?.[`${rule.key}_pix`] ?? (Number(tableData[`${rule.key}_pix`]) || 0);
      });

      if (existingId) {
        await base44.entities.CaixaConferencia.update(existingId, payload);
      } else {
        await base44.entities.CaixaConferencia.create(payload);
      }

      await loadRecords();

      let msg = `Conferência concluída com sucesso! ${processedCount} registro(s) processado(s).`;
      if (notFound.length > 0) {
        msg += ` Formas não encontradas no arquivo (preenchidas com R$ 0,00): ${notFound.join(", ")}.`;
      }
      setImportMsg(msg);
    } catch (error) {
      setImportErr(`Erro ao importar arquivo: ${error.message || error}`);
    }
    setImporting(false);
    setImportType("");
    e.target.value = "";
  };

  const handlePagBankFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!header.company_id || !header.date) {
      setImportErr("Selecione a empresa e a data antes de importar.");
      e.target.value = "";
      return;
    }
    setImporting(true);
    setImportType("pagbank");
    setImportErr("");
    setImportMsg("");
    try {
      const text = await file.text();
      const { values, notFound } = processPagBankCSV(text);

      const newTable = { ...tableData };
      PAGBANK_KEYS.forEach((key) => {
        newTable[`${key}_site`] = values[key] || 0;
      });
      setTableData(newTable);

      let msg = "PagBank: coluna SITE preenchida com sucesso!";
      if (notFound.length > 0) {
        msg += ` Formas não encontradas no arquivo (preenchidas com R$ 0,00): ${notFound.join(", ")}.`;
      }
      setImportMsg(msg);
    } catch (error) {
      setImportErr(`Erro ao importar PagBank: ${error.message || error}`);
    }
    setImporting(false);
    setImportType("");
    e.target.value = "";
  };

  const handlePremmiaFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!header.company_id || !header.date) {
      setImportErr("Selecione a empresa e a data antes de importar.");
      e.target.value = "";
      return;
    }
    setImporting(true);
    setImportType("premmia");
    setImportErr("");
    setImportMsg("");
    try {
      const { file_url } = await base44.integrations.Core.UploadFile({ file });
      const result = await base44.integrations.Core.ExtractDataFromUploadedFile({
        file_url,
        json_schema: {
          type: "object",
          properties: {
            rows: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  "Forma de Pagamento": { type: "string" },
                  "Valor líquido": { type: "string" },
                },
              },
            },
          },
        },
      });
      const extracted = Array.isArray(result.output) ? result.output : result.output?.rows || [];
      const newDetalheRows = processPremmiaRows(extracted);
      setDetalheRows(newDetalheRows);

      setTableData((td) => {
        const next = { ...td };
        DETALHE_COLS.forEach((dc) => {
          const total = newDetalheRows.reduce((s, r) => s + (Number(r[dc.key]) || 0), 0);
          if (total > 0) next[`${dc.premmiaKey}_site`] = total;
        });
        return next;
      });

      setImportMsg(`PREMMIA: ${extracted.length} transação(ões) processada(s). Tabela de detalhamento preenchida.`);
    } catch (error) {
      setImportErr(`Erro ao importar PREMMIA: ${error.message || error}`);
    }
    setImporting(false);
    setImportType("");
    e.target.value = "";
  };

  const handleSave = async () => {
    if (!header.company_id || !header.date) return;
    setSaving(true);
    const company = companies.find((c) => c.id === header.company_id);

    // Merge detalhe totals into tableData before saving
    const finalTable = computeTableWithDetalhe(tableData, detalheRows);
    // PAG PIX SITE = total da coluna PIX
    finalTable.pag_pix_site = ROWS.reduce((s, r) => s + (Number(finalTable[`${r.key}_pix`]) || 0), 0);

    const payload = {
      company_id: header.company_id,
      company_name: company?.name || "",
      date: header.date,
      shift: header.shift || "",
      notes: header.notes || "",
      detalhe_cartao: JSON.stringify(detalheRows.map((r) => r.cartao)),
      detalhe_pix:    JSON.stringify(detalheRows.map((r) => r.pix)),
      detalhe_vale:   JSON.stringify(detalheRows.map((r) => r.vale)),
      detalhe_cupom:  JSON.stringify(detalheRows.map((r) => r.cupom)),
    };
    ROWS.forEach((r) => {
      payload[`${r.key}_sistema`] = Number(finalTable[`${r.key}_sistema`]) || 0;
      payload[`${r.key}_site`]    = Number(finalTable[`${r.key}_site`])    || 0;
      payload[`${r.key}_pix`]     = Number(finalTable[`${r.key}_pix`])     || 0;
    });

    if (editingId) {
      await base44.entities.CaixaConferencia.update(editingId, payload);
    } else {
      await base44.entities.CaixaConferencia.create(payload);
    }
    setSaving(false);
    resetForm();
    setShowForm(false);
    await loadRecords();
  };

  const filteredRecords = records.filter((r) => {
    if (filterCompany !== "all" && r.company_id !== filterCompany) return false;
    if (filterDate && r.date !== filterDate) return false;
    return true;
  });

  const fmt = (dateStr) =>
    dateStr ? new Date(dateStr + "T12:00:00").toLocaleDateString("pt-BR") : "-";

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-24">
      {printRecord && <PrintCaixa record={printRecord} detalheRows={(() => {
        try {
          const cartao = JSON.parse(printRecord.detalhe_cartao || "[]");
          const pix    = JSON.parse(printRecord.detalhe_pix    || "[]");
          const vale   = JSON.parse(printRecord.detalhe_vale   || "[]");
          const cupom  = JSON.parse(printRecord.detalhe_cupom  || "[]");
          const len = Math.max(cartao.length, pix.length, vale.length, cupom.length);
          return Array.from({ length: len }, (_, i) => ({ cartao: cartao[i]??0, pix: pix[i]??0, vale: vale[i]??0, cupom: cupom[i]??0 }));
        } catch { return []; }
      })()} />}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-heading font-bold text-foreground">Conferência de Caixas</h1>
          <p className="text-sm text-muted-foreground mt-1">Lançamento e conferência diária por categoria</p>
        </div>
        <Button onClick={() => { resetForm(); setShowForm(!showForm); }} className="gap-2">
          {showForm && !editingId ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          {showForm && !editingId ? "Ocultar" : "Nova Conferência"}
        </Button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="bg-card rounded-xl border border-border p-5 space-y-6">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-semibold text-foreground">{editingId ? "Editar Conferência" : "Nova Conferência de Caixa"}</h2>
            <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={handleImportFile} />
            <input ref={pagBankFileRef} type="file" accept=".csv" className="hidden" onChange={handlePagBankFile} />
            <input ref={premmiaFileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handlePremmiaFile} />
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={importing} className="gap-2">
                {importType === "caixa" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                Arquivo Caixa
              </Button>
              <Button variant="outline" size="sm" onClick={() => pagBankFileRef.current?.click()} disabled={importing} className="gap-2">
                {importType === "pagbank" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                PagBank
              </Button>
              <Button variant="outline" size="sm" onClick={() => premmiaFileRef.current?.click()} disabled={importing} className="gap-2">
                {importType === "premmia" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                PREMMIA
              </Button>
            </div>
          </div>

          {importMsg && (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg p-3 text-sm">
              {importMsg}
            </div>
          )}
          {importErr && (
            <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">
              {importErr}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Empresa *</Label>
              <Select value={header.company_id} onValueChange={(v) => setHeader({ ...header, company_id: v })}>
                <SelectTrigger><SelectValue placeholder="Selecionar empresa" /></SelectTrigger>
                <SelectContent>
                  {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Data *</Label>
              <Input type="date" value={header.date} onChange={(e) => setHeader({ ...header, date: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Turno</Label>
              <Select value={header.shift} onValueChange={(v) => setHeader({ ...header, shift: v })}>
                <SelectTrigger><SelectValue placeholder="Selecionar (opcional)" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Primeiro Turno">Primeiro Turno</SelectItem>
                  <SelectItem value="Segundo Turno">Segundo Turno</SelectItem>
                  <SelectItem value="Terceiro Turno">Terceiro Turno</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Observações</Label>
            <Textarea value={header.notes} onChange={(e) => setHeader({ ...header, notes: e.target.value })} placeholder="Observações..." rows={2} />
          </div>

          {/* ── TABELA PRINCIPAL ── */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Tabela Principal</p>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/60">
                    <th className="text-left px-3 py-2 font-semibold border-r border-border min-w-[170px]">Categoria</th>
                    <th className="text-center px-3 py-2 font-semibold border-r border-border w-36">SISTEMA</th>
                    <th className="text-center px-3 py-2 font-semibold border-r border-border w-36">
                      SITE
                      <span className="block text-[10px] font-normal text-muted-foreground">(auto das premmias)</span>
                    </th>
                    <th className="text-center px-3 py-2 font-semibold border-r border-border w-36">DIFERENÇA</th>
                    <th className="text-center px-3 py-2 font-semibold w-36">PIX</th>
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row, i) => {
                    const isPremia = DETALHE_COLS.some((dc) => dc.premmiaKey === row.key);
                    const sistema = Number(tableData[`${row.key}_sistema`]) || 0;
                    const site = Number(tableData[`${row.key}_site`]) || 0;
                    const diferenca = sistema - site;
                    return (
                      <tr key={row.key} className={i % 2 === 0 ? "bg-background" : "bg-muted/20"}>
                        <td className="px-3 py-1.5 font-medium border-r border-border text-foreground">{row.label}</td>
                        <td className="px-2 py-1 border-r border-border">
                          <div className="flex items-center gap-0.5">
                            <span className="text-xs text-muted-foreground">R$</span>
                            <TableNumberInput
                              value={tableData[`${row.key}_sistema`]}
                              onChange={(e) => setCell(`${row.key}_sistema`, e.target.value)}
                              placeholder="0,00"
                            />
                          </div>
                        </td>
                        <td className="px-2 py-1 border-r border-border">
                          {isPremia ? (
                            <div className="h-7 flex items-center justify-center text-xs font-semibold text-primary tabular-nums">
                              {formatCurrency(site)}
                            </div>
                          ) : row.key === "pag_pix" ? (
                            <div className="h-7 flex items-center justify-center text-xs font-semibold text-primary tabular-nums">
                              {formatCurrency(site)}
                            </div>
                          ) : (
                            <div className="flex items-center gap-0.5">
                              <span className="text-xs text-muted-foreground">R$</span>
                              <TableNumberInput
                                value={tableData[`${row.key}_site`]}
                                onChange={(e) => setCell(`${row.key}_site`, e.target.value)}
                                placeholder="0,00"
                              />
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-1 border-r border-border">
                          <div className={`h-7 flex items-center justify-center text-xs font-bold tabular-nums ${diferenca >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                            {formatCurrency(diferenca)}
                          </div>
                        </td>
                        <td className="px-2 py-1">
                          <div className="flex items-center gap-0.5">
                            <span className="text-xs text-muted-foreground">R$</span>
                            <TableNumberInput
                              value={tableData[`${row.key}_pix`]}
                              onChange={(e) => setCell(`${row.key}_pix`, e.target.value)}
                              placeholder="0,00"
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="bg-primary/10 font-bold border-t-2 border-primary/30">
                    <td className="px-3 py-2 border-r border-border">TOTAL</td>
                    <td className="px-3 py-2 text-center tabular-nums border-r border-border">
                      {formatCurrency(colSum(tableData, "sistema"))}
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums border-r border-border">
                      {formatCurrency(colSum(tableData, "site"))}
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums border-r border-border">
                      {(() => {
                        const d = colSum(tableData, "sistema") - colSum(tableData, "site");
                        return <span className={d >= 0 ? "text-emerald-600" : "text-red-600"}>{formatCurrency(d)}</span>;
                      })()}
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums">
                      {formatCurrency(colSum(tableData, "pix"))}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* ── TABELA INFERIOR (detalhe premmias) ── */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              Detalhamento PREMMIA — os totais alimentam automaticamente a coluna SITE acima
            </p>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/60">
                    <th className="text-center px-3 py-2 font-semibold border-r border-border w-10">#</th>
                    {DETALHE_COLS.map((dc, ci) => (
                      <th key={dc.key} className={`text-center px-3 py-2 font-semibold ${ci < DETALHE_COLS.length - 1 ? "border-r border-border" : ""}`}>
                        {dc.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {detalheRows.map((row, i) => (
                    <tr key={i} className={i % 2 === 0 ? "bg-background" : "bg-muted/20"}>
                      <td className="px-2 py-1 text-center text-xs text-muted-foreground border-r border-border">{i + 1}</td>
                      {DETALHE_COLS.map((dc, ci) => (
                        <td key={dc.key} className={`px-2 py-1 ${ci < DETALHE_COLS.length - 1 ? "border-r border-border" : ""}`}>
                          <TableNumberInput
                            value={row[dc.key]}
                            onChange={(e) => setDetalheCell(i, dc.key, e.target.value)}
                            placeholder="0,00"
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-primary/10 font-bold border-t-2 border-primary/30">
                    <td className="px-3 py-2 border-r border-border text-xs text-center">TOTAL</td>
                    {DETALHE_COLS.map((dc, ci) => (
                      <td key={dc.key} className={`px-3 py-2 text-center tabular-nums ${ci < DETALHE_COLS.length - 1 ? "border-r border-border" : ""}`}>
                        {formatCurrency(detalheColSum(detalheRows, dc.key))}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              </table>
            </div>
            <Button variant="ghost" size="sm" onClick={addDetalheRow} className="mt-2 gap-1 text-xs text-muted-foreground">
              <PlusCircle className="w-3.5 h-3.5" /> Adicionar linha
            </Button>
          </div>

          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => { resetForm(); setShowForm(false); }}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving} className="gap-2">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {editingId ? "Atualizar" : "Salvar"}
            </Button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <Label className="text-xs">Empresa</Label>
          <Select value={filterCompany} onValueChange={setFilterCompany}>
            <SelectTrigger className="w-44 h-8 text-sm"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Data</Label>
          <Input type="date" value={filterDate} onChange={(e) => setFilterDate(e.target.value)} className="w-36 h-8 text-sm" />
        </div>
        {filterDate && (
          <Button variant="ghost" size="sm" onClick={() => setFilterDate("")} className="text-xs">Limpar</Button>
        )}
      </div>

      {/* Records list */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>
      ) : filteredRecords.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg font-medium">Nenhuma conferência encontrada</p>
          <p className="text-sm mt-1">Clique em "Nova Conferência" para começar</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredRecords.map((record) => (
            <RecordCard
              key={record.id}
              record={record}
              onEdit={() => handleEdit(record)}
              onDelete={() => handleDelete(record.id)}
              onPrint={() => { setPrintRecord(record); setTimeout(() => window.print(), 300); }}
              fmt={fmt}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RecordCard({ record, onEdit, onDelete, onPrint, fmt }) {
  const [expanded, setExpanded] = useState(false);
  const totalSistema = ROWS.reduce((s, r) => s + (Number(record[`${r.key}_sistema`]) || 0), 0);
  const totalSite    = ROWS.reduce((s, r) => s + (Number(record[`${r.key}_site`])    || 0), 0);
  const totalPix     = ROWS.reduce((s, r) => s + (Number(record[`${r.key}_pix`])     || 0), 0);

  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 flex-wrap gap-2">
        <div className="flex items-center gap-3 flex-wrap">
          <button onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          <div>
            <p className="font-semibold text-foreground text-sm">{record.company_name}</p>
            <p className="text-xs text-muted-foreground">{fmt(record.date)}{record.shift ? ` · ${record.shift}` : ""}</p>
          </div>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <div className="text-right text-xs"><p className="text-muted-foreground">Sistema</p><p className="font-semibold tabular-nums">{formatCurrency(totalSistema)}</p></div>
          <div className="text-right text-xs"><p className="text-muted-foreground">Site</p><p className="font-semibold tabular-nums">{formatCurrency(totalSite)}</p></div>
          <div className="text-right text-xs">
            <p className="text-muted-foreground">Diferença</p>
            <p className={`font-semibold tabular-nums ${totalSistema - totalSite >= 0 ? "text-emerald-600" : "text-red-600"}`}>{formatCurrency(totalSistema - totalSite)}</p>
          </div>
          <div className="text-right text-xs"><p className="text-muted-foreground">PIX</p><p className="font-semibold tabular-nums">{formatCurrency(totalPix)}</p></div>
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onPrint}><Printer className="w-4 h-4" /></Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}><Pencil className="w-4 h-4" /></Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive"><Trash2 className="w-4 h-4" /></Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Excluir conferência?</AlertDialogTitle>
                  <AlertDialogDescription>Esta ação não pode ser desfeita.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction onClick={onDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Excluir</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-muted/50">
                <th className="text-left px-3 py-2 font-semibold border-r border-border">Categoria</th>
                <th className="text-center px-3 py-2 font-semibold border-r border-border">SISTEMA</th>
                <th className="text-center px-3 py-2 font-semibold border-r border-border">SITE</th>
                <th className="text-center px-3 py-2 font-semibold border-r border-border">DIFERENÇA</th>
                <th className="text-center px-3 py-2 font-semibold">PIX</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row, i) => {
                const s  = Number(record[`${row.key}_sistema`]) || 0;
                const si = Number(record[`${row.key}_site`])    || 0;
                const p  = Number(record[`${row.key}_pix`])     || 0;
                const d  = s - si;
                if (s === 0 && si === 0 && p === 0) return null;
                return (
                  <tr key={row.key} className={i % 2 === 0 ? "bg-background" : "bg-muted/10"}>
                    <td className="px-3 py-1.5 font-medium border-r border-border">{row.label}</td>
                    <td className="px-3 py-1.5 text-center border-r border-border tabular-nums">{formatCurrency(s)}</td>
                    <td className="px-3 py-1.5 text-center border-r border-border tabular-nums">{formatCurrency(si)}</td>
                    <td className={`px-3 py-1.5 text-center border-r border-border tabular-nums font-semibold ${d >= 0 ? "text-emerald-600" : "text-red-600"}`}>{formatCurrency(d)}</td>
                    <td className="px-3 py-1.5 text-center tabular-nums">{formatCurrency(p)}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="bg-primary/10 font-bold border-t border-primary/20">
                <td className="px-3 py-2 border-r border-border">TOTAL</td>
                <td className="px-3 py-2 text-center border-r border-border tabular-nums">{formatCurrency(totalSistema)}</td>
                <td className="px-3 py-2 text-center border-r border-border tabular-nums">{formatCurrency(totalSite)}</td>
                <td className={`px-3 py-2 text-center border-r border-border tabular-nums ${totalSistema - totalSite >= 0 ? "text-emerald-600" : "text-red-600"}`}>{formatCurrency(totalSistema - totalSite)}</td>
                <td className="px-3 py-2 text-center tabular-nums">{formatCurrency(totalPix)}</td>
              </tr>
            </tfoot>
          </table>
          {record.notes && (
            <div className="px-3 py-2 text-xs text-muted-foreground border-t border-border">
              <span className="font-medium">Obs:</span> {record.notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PrintCaixa({ record, detalheRows = [] }) {
  if (!record) return null;
  const fmt = (d) => d ? new Date(d + "T12:00:00").toLocaleDateString("pt-BR") : "-";
  const totalSistema = ROWS.reduce((s, r) => s + (Number(record[`${r.key}_sistema`]) || 0), 0);
  const totalSite    = ROWS.reduce((s, r) => s + (Number(record[`${r.key}_site`])    || 0), 0);
  const totalPix     = ROWS.reduce((s, r) => s + (Number(record[`${r.key}_pix`])     || 0), 0);

  return (
    <div className="hidden print:block fixed inset-0 bg-white z-[9999] p-4">
      <div className="max-w-2xl mx-auto font-sans text-xs">
        <div className="text-center border border-black mb-0">
          <div className="border-b border-black py-1 px-2">
            <h1 className="text-sm font-bold">CONFERÊNCIA DE CAIXAS</h1>
          </div>
          <div className="py-1 px-2 flex justify-between">
            <span><b>{record.company_name}</b></span>
            <span>Data: <b>{fmt(record.date)}</b></span>
            {record.shift && <span>Turno: <b>{record.shift}</b></span>}
          </div>
        </div>

        <table className="w-full border-collapse border border-black">
          <thead>
            <tr>
              <th className="border border-black px-2 py-1 text-left">Categoria</th>
              <th className="border border-black px-2 py-1 text-right">SISTEMA</th>
              <th className="border border-black px-2 py-1 text-right">SITE</th>
              <th className="border border-black px-2 py-1 text-right">DIFERENÇA</th>
              <th className="border border-black px-2 py-1 text-right">PIX</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const s = Number(record[`${row.key}_sistema`]) || 0;
              const si = Number(record[`${row.key}_site`]) || 0;
              const d = s - si;
              return (
              <tr key={row.key}>
                <td className="border border-black px-2 py-0.5">{row.label}</td>
                <td className="border border-black px-2 py-0.5 text-right tabular-nums">{formatCurrency(s)}</td>
                <td className="border border-black px-2 py-0.5 text-right tabular-nums">{formatCurrency(si)}</td>
                <td className="border border-black px-2 py-0.5 text-right tabular-nums">{formatCurrency(d)}</td>
                <td className="border border-black px-2 py-0.5 text-right tabular-nums">{formatCurrency(Number(record[`${row.key}_pix`]) || 0)}</td>
              </tr>
            )})}
          </tbody>
          <tfoot>
            <tr className="font-bold">
              <td className="border border-black px-2 py-1">TOTAL</td>
              <td className="border border-black px-2 py-1 text-right tabular-nums">{formatCurrency(totalSistema)}</td>
              <td className="border border-black px-2 py-1 text-right tabular-nums">{formatCurrency(totalSite)}</td>
              <td className="border border-black px-2 py-1 text-right tabular-nums">{formatCurrency(totalSistema - totalSite)}</td>
              <td className="border border-black px-2 py-1 text-right tabular-nums">{formatCurrency(totalPix)}</td>
            </tr>
          </tfoot>
        </table>

        {detalheRows.length > 0 && (
          <>
            <div className="mt-3 mb-1 font-bold">Detalhamento PREMMIA</div>
            <table className="w-full border-collapse border border-black">
              <thead>
                <tr>
                  <th className="border border-black px-2 py-1">#</th>
                  {DETALHE_COLS.map((dc) => (
                    <th key={dc.key} className="border border-black px-2 py-1 text-right">{dc.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detalheRows.map((row, i) => (
                  <tr key={i}>
                    <td className="border border-black px-2 py-0.5 text-center">{i + 1}</td>
                    {DETALHE_COLS.map((dc) => (
                      <td key={dc.key} className="border border-black px-2 py-0.5 text-right tabular-nums">
                        {Number(row[dc.key]) ? formatCurrency(Number(row[dc.key])) : ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-bold">
                  <td className="border border-black px-2 py-1 text-center">TOTAL</td>
                  {DETALHE_COLS.map((dc) => (
                    <td key={dc.key} className="border border-black px-2 py-1 text-right tabular-nums">
                      {formatCurrency(detalheRows.reduce((s, r) => s + (Number(r[dc.key]) || 0), 0))}
                    </td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </>
        )}

        {record.notes && (
          <div className="border border-black border-t-0 px-2 py-1"><b>Obs:</b> {record.notes}</div>
        )}
        <div className="mt-8 text-center">
          <div className="border-t border-black pt-2 inline-block w-56">
            <p className="text-gray-500">Assinatura do Conferente</p>
          </div>
        </div>
      </div>
    </div>
  );
}

O sistema de cartões deve funcionar da seguinte forma:
somar os valores
BR PREMMIA CARTAO + CARTAO PREMIA
BR PREMMIA GENERICO
BR PREMMIA PIX
BR PREMMIA VALE
CARTAO FITCARD
PAG PIX
POS PAGSEGURO AMERICAN EXPRESS + SMART PAGSEGURO AMERICAN EXPRESS
POS PAGSEGURO ELO CREDITO + SMART PAGSEGURO ELO CRED
POS PAGSEGURO ELO DEBITO + SMART PAGSEGURO ELO DEBI
POS PAGSEGURO MASTER.CRE + SMART PAGSEGURO MASTER.C
POS PAGSEGURO MASTER.DEB + SMART PAGSEGURO MASTER.D
POS PAGSEGURO VISA CREDI + SMART PAGSEGURO VISA CRE
POS PAGSEGURO VISA DEBIT + SMART PAGSEGURO VISA DEB

FAZER O RELATORIO NO MODELO


PREMMIA CARTAO = SOMA DO VALOR DA SOMA DO BR PREMMIA CARTAO + CARTAO PREMIA
PREMMIA PIX = AO VALOR DO BR PREMMIA PIX
PREMMIA VALE = AO VALOR DO BR PREMMIA VALE
PREMMIA CUPOM = AO VALOR DO BR PREMMIA GENERICO
CARTAO FITCARD = AO VALOR DO CARTAO FITCARD
PAG PIX = AO VALOR DO PAG PIX
AMERICAN EXP = AO VALOR DO POS PAGSEGURO AMERICAN EXPRESS + SMART PAGSEGURO AMERICAN EXPRESS
ELO CREDITO = AO VALOR DA SOMA DO POS PAGSEGURO ELO CREDITO + SMART PAGSEGURO ELO CRED
ELO DEBITO = AO VALOR DA SOMA DO POS PAGSEGURO ELO DEBITO + SMART PAGSEGURO ELO DEBI
MASTER.CREDITO = AO VALOR DA SOMA DO POS PAGSEGURO MASTER.CRE + SMART PAGSEGURO MASTER.C
MASTER.DEBITO = AO VALOR DA SOMA DO POS PAGSEGURO MASTER.DEB + SMART PAGSEGURO MASTER.D
VISA CREDITO = AO VALOR DA SOMA DO POS PAGSEGURO VISA CREDI + SMART PAGSEGURO VISA CRE
VISA DEBITO = AO VALOR DA SOMA DO POS PAGSEGURO VISA DEBIT + SMART PAGSEGURO VISA DEB

o sistema deve possuir uma área para configuração onde o usuário poderá definir quais categorias de cartões pertencem a cada grupo (ex: AMERICAN EXPRESS, ELO CREDITO, etc.). Isso permitirá que o sistema seja flexível e adaptável a diferentes tipos de cartões e fornecedores e determinar como acontece a soma dos valores de cada grupo.

os relatórios de importação estão em ./relatorios você pode usa-los como referência.