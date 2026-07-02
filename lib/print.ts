// Cetak dokumen per-transaksi: Faktur & Surat Jalan.
// Membuka jendela baru berisi HTML rapi lalu memanggil dialog print
// (pengguna bisa pilih "Save as PDF").

export type InvoiceDetail = {
  number: string; date: string; due_date: string | null; status: string;
  notes: string | null; subtotal: string; tax_total: string; total: string;
  paid_total: string; warehouse: string | null;
  contact: { name: string; address: string | null; phone: string | null; npwp: string | null };
  lines: { description: string; quantity: string; unit_price: string; discount: string; tax_rate: string; line_total: string }[];
};
export type CompanyInfo = { name: string; npwp: string | null; address: string | null };

const rp = (v: string | number) =>
  "Rp " + Number(v).toLocaleString("id-ID", { maximumFractionDigits: 0 });
const tgl = (s: string) =>
  new Date(s + "T00:00:00").toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });

const BASE_CSS = `
  *{box-sizing:border-box} body{font-family:Arial,sans-serif;color:#1b2a26;margin:0;padding:28px}
  .head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}
  .co h1{font-size:20px;margin:0;color:#24564a} .co p{margin:2px 0;font-size:11px;color:#666}
  .doc{text-align:right} .doc h2{font-size:22px;margin:0;letter-spacing:1px;color:#24564a}
  .doc p{margin:2px 0;font-size:12px}
  .meta{display:flex;justify-content:space-between;gap:24px;margin:14px 0 18px}
  .meta .box{font-size:12px;line-height:1.5} .meta b{display:block;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th{background:#eef4f1;text-align:left;padding:7px 8px;border:1px solid #d8e2dd;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#4a5a53}
  td{padding:7px 8px;border:1px solid #e3eae6} .r{text-align:right}
  .tot{margin-top:12px;margin-left:auto;width:260px;font-size:12.5px}
  .tot div{display:flex;justify-content:space-between;padding:3px 0}
  .tot .grand{border-top:2px solid #24564a;margin-top:4px;padding-top:6px;font-weight:bold;font-size:14px}
  .sign{display:flex;justify-content:space-between;margin-top:44px;font-size:12px;text-align:center}
  .sign div{width:180px} .sign .line{margin-top:56px;border-top:1px solid #999;padding-top:4px}
  .note{margin-top:14px;font-size:11px;color:#777;font-style:italic}
  @media print {.no-print{display:none}}
`;

function openAndPrint(title: string, body: string) {
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(`<!doctype html><html><head><title>${title}</title><style>${BASE_CSS}</style></head><body>${body}<script>window.onload=function(){window.print()}</script></body></html>`);
  w.document.close();
}

export function printInvoiceDoc(inv: InvoiceDetail, co: CompanyInfo) {
  const rows = inv.lines.map((l, i) => `
    <tr><td class="r" style="width:34px">${i + 1}</td>
    <td>${l.description}</td>
    <td class="r">${Number(l.quantity)}</td>
    <td class="r">${rp(l.unit_price)}</td>
    <td class="r">${Number(l.discount) > 0 ? rp(l.discount) : "—"}</td>
    <td class="r">${rp(l.line_total)}</td></tr>`).join("");
  const sisa = Number(inv.total) - Number(inv.paid_total);
  const body = `
    <div class="head">
      <div class="co"><h1>${co.name}</h1>
        ${co.address ? `<p>${co.address}</p>` : ""}${co.npwp ? `<p>NPWP: ${co.npwp}</p>` : ""}</div>
      <div class="doc"><h2>FAKTUR</h2><p><b>${inv.number}</b></p><p>${tgl(inv.date)}</p></div>
    </div>
    <div class="meta">
      <div class="box"><b>Kepada</b>${inv.contact.name}${inv.contact.address ? `<br/>${inv.contact.address}` : ""}${inv.contact.phone ? `<br/>Telp: ${inv.contact.phone}` : ""}</div>
      <div class="box" style="text-align:right"><b>Jatuh Tempo</b>${inv.due_date ? tgl(inv.due_date) : "—"}</div>
    </div>
    <table><thead><tr><th class="r">No</th><th>Deskripsi</th><th class="r">Qty</th><th class="r">Harga</th><th class="r">Diskon</th><th class="r">Jumlah</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <div class="tot">
      <div><span>Subtotal</span><span>${rp(inv.subtotal)}</span></div>
      <div><span>Pajak</span><span>${rp(inv.tax_total)}</span></div>
      <div class="grand"><span>Total</span><span>${rp(inv.total)}</span></div>
      ${Number(inv.paid_total) > 0 ? `<div><span>Terbayar</span><span>${rp(inv.paid_total)}</span></div><div><span>Sisa</span><span>${rp(sisa)}</span></div>` : ""}
    </div>
    ${inv.notes ? `<p class="note">Catatan: ${inv.notes}</p>` : ""}
    <div class="sign"><div>Hormat kami,<div class="line">${co.name}</div></div>
    <div>Penerima,<div class="line">${inv.contact.name}</div></div></div>`;
  openAndPrint(`Faktur ${inv.number}`, body);
}

export function printDeliveryNote(inv: InvoiceDetail, co: CompanyInfo) {
  const rows = inv.lines.map((l, i) => `
    <tr><td class="r" style="width:34px">${i + 1}</td>
    <td>${l.description}</td>
    <td class="r">${Number(l.quantity)}</td>
    <td style="width:170px"></td></tr>`).join("");
  const body = `
    <div class="head">
      <div class="co"><h1>${co.name}</h1>
        ${co.address ? `<p>${co.address}</p>` : ""}</div>
      <div class="doc"><h2>SURAT JALAN</h2><p><b>${inv.number}</b></p><p>${tgl(inv.date)}</p></div>
    </div>
    <div class="meta">
      <div class="box"><b>Dikirim kepada</b>${inv.contact.name}${inv.contact.address ? `<br/>${inv.contact.address}` : ""}${inv.contact.phone ? `<br/>Telp: ${inv.contact.phone}` : ""}</div>
      <div class="box" style="text-align:right"><b>Gudang asal</b>${inv.warehouse ?? "—"}</div>
    </div>
    <table><thead><tr><th class="r">No</th><th>Barang</th><th class="r">Qty</th><th>Keterangan</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="note">Barang telah diterima dalam keadaan baik dan jumlah sesuai.</p>
    <div class="sign">
      <div>Pengirim,<div class="line">&nbsp;</div></div>
      <div>Sopir/Kurir,<div class="line">&nbsp;</div></div>
      <div>Penerima,<div class="line">&nbsp;</div></div>
    </div>`;
  openAndPrint(`Surat Jalan ${inv.number}`, body);
}
