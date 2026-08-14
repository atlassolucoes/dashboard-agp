import os 
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1HMuQfuLAw_GrWmg-H-kQykXxHtV0U3BPDBCsEy96858"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def get_service():
    creds_json = os.environ["GOOGLE_CREDENTIALS"]
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

def read_sheet(service, range_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name
    ).execute()
    return result.get("values", [])

def parse_valor(v):
    if not v: return 0.0
    v = str(v).strip().replace("R$", "").replace(" ", "")
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return round(float(v), 2)
    except:
        return 0.0

def parse_date(d):
    if not d: return None
    d = str(d).strip()
    if "/" in d:
        parts = d.split("/")
        if len(parts) == 3:
            dd, mm, yyyy = parts[0], parts[1], parts[2][:4]
            return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    if "-" in d and len(d) >= 10:
        return d[:10]
    return None

def get_col(row, header, col_name, default=""):
    try:
        idx = header.index(col_name)
        return str(row[idx]).strip() if idx < len(row) else default
    except ValueError:
        return default

def process_despesas(rows):
    if not rows: return []
    header = rows[0]
    records = []
    for row in rows[1:]:
        dt = parse_date(get_col(row, header, "DATA"))
        valor = parse_valor(get_col(row, header, "VALOR (R$)"))
        if not dt or valor == 0: continue
        status = get_col(row, header, "STATUS")
        if status == "Permuta": continue
        records.append({
            "data": dt, "mes": dt[:7],
            "fornecedor": get_col(row, header, "FORNECEDOR"),
            "descricao": get_col(row, header, "DESCRIÇÃO"),
            "tag": get_col(row, header, "TAG"),
            "categoria": get_col(row, header, "CATEGORIA"),
            "subcategoria": get_col(row, header, "SUB-CATEGORIA"),
            "modelo": get_col(row, header, "MODELO"),
            "valor": valor,
            "status": status,
            "pago_por": get_col(row, header, "PAGO POR"),
        })
    return records

def process_receitas(rows):
    """Lê exportação direta da NuvemShop colada no Sheets."""
    if not rows: return []
    header = rows[0]
    records = []
    for row in rows[1:]:
        # Só pedidos confirmados
        status_pag = get_col(row, header, "Status do Pagamento")
        if status_pag != "Confirmado": continue

        dt = parse_date(get_col(row, header, "Data de pagamento"))
        if not dt: continue

        total = parse_valor(get_col(row, header, "Total"))
        if total == 0: continue

        num_pedido = get_col(row, header, "Número do Pedido")
        try: pedido = int(num_pedido)
        except: pedido = 0

        meio = get_col(row, header, "Meio de pagamento")
        cupom = get_col(row, header, "Cupom de Desconto")
        comprador = get_col(row, header, "Nome do comprador")
        produto = get_col(row, header, "Nome do Produto")

        records.append({
            "data": dt, "mes": dt[:7],
            "pedido": pedido,
            "produto": produto,
            "cupom": cupom,
            "valor": total,
            "comprador": comprador,
            "meio_pagamento": meio,
        })
    return records

def process_aportes(rows):
    if not rows: return []
    header = rows[0]
    TIPO_MAP = {
        "Aporte DD Business": "APORTE_DD",
        "Aporte Agroplay Music": "APORTE_MUSIC",
        "Patrocínio": "PATROCINIO",
        "Repasse Vendas": "REPASSE_VENDAS",
        "Rendimento": "RENDIMENTO",
    }
    records = []
    for row in rows[1:]:
        dt = parse_date(get_col(row, header, "DATA"))
        valor = parse_valor(get_col(row, header, "VALOR (R$)"))
        if not dt or valor == 0: continue
        tipo_label = get_col(row, header, "TIPO")
        tipo = TIPO_MAP.get(tipo_label, "PATROCINIO")
        nome = get_col(row, header, "NOME")
        records.append({
            "data": dt, "mes": dt[:7],
            "produto_raw": nome, "nome": nome,
            "tipo": tipo,
            "descricao": get_col(row, header, "DESCRIÇÃO"),
            "valor": valor,
        })
    return records

def update_html(data):
    html_path = "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    data_json = json.dumps(data, ensure_ascii=False)

    marker_start = "const DATA="
    marker_end = ";\nconst fmt="
    ds = html.index(marker_start) + len(marker_start)
    de = html.index(marker_end)
    html = html[:ds] + data_json + html[de:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML atualizado: {len(data['despesas'])} despesas | {len(data['receitas'])} receitas | {len(data['aportes'])} aportes")

def main():
    service = get_service()

    print("📋 Lendo DESPESAS...")
    despesas = process_despesas(read_sheet(service, "DESPESAS!A:Z"))
    print(f"   {len(despesas)} registros")

    print("🛒 Lendo RECEITAS (NuvemShop)...")
    receitas = process_receitas(read_sheet(service, "RECEITAS!A:BH"))
    print(f"   {len(receitas)} registros")

    print("💰 Lendo APORTES...")
    aportes = process_aportes(read_sheet(service, "APORTES!A:Z"))
    print(f"   {len(aportes)} registros")

    all_months = sorted(set(
        [r["mes"] for r in despesas] +
        [r["mes"] for r in receitas] +
        [r["mes"] for r in aportes]
    ))

    data = {
        "despesas": despesas,
        "receitas": receitas,
        "aportes": aportes,
        "meses": all_months,
    }

    update_html(data)

if __name__ == "__main__":
    main()
