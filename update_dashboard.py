import os
import json
import re
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
    v = str(v).strip()
    v = v.replace("R$", "").replace(" ", "")
    # Handle Brazilian format: 1.234,56 -> 1234.56
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return round(float(v), 2)
    except:
        return 0.0

def parse_date(d):
    if not d: return None
    d = str(d).strip()
    # DD/MM/YYYY
    if "/" in d:
        parts = d.split("/")
        if len(parts) == 3:
            dd, mm, yyyy = parts
            return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    return None

def process_despesas(rows):
    if not rows: return []
    header = rows[0]
    records = []
    for row in rows[1:]:
        # Pad row
        while len(row) < len(header): row.append("")
        def g(col):
            try: return str(row[header.index(col)]).strip() if col in header else ""
            except: return ""
        
        dt = parse_date(g("DATA"))
        valor = parse_valor(g("VALOR (R$)"))
        if not dt or valor == 0: continue
        
        records.append({
            "data": dt,
            "mes": dt[:7],
            "fornecedor": g("FORNECEDOR"),
            "descricao": g("DESCRIÇÃO"),
            "tag": g("TAG"),
            "categoria": g("CATEGORIA"),
            "subcategoria": g("SUB-CATEGORIA"),
            "modelo": g("MODELO"),
            "valor": valor,
            "status": g("STATUS"),
            "pago_por": g("PAGO POR"),
        })
    return records

def process_receitas(rows):
    if not rows: return []
    header = rows[0]
    records = []
    for row in rows[1:]:
        while len(row) < len(header): row.append("")
        def g(col):
            try: return str(row[header.index(col)]).strip() if col in header else ""
            except: return ""
        
        dt = parse_date(g("DATA"))
        valor = parse_valor(g("VALOR (R$)"))
        if not dt or valor == 0: continue
        
        records.append({
            "data": dt,
            "mes": dt[:7],
            "pedido": int(g("Nº PEDIDO")) if g("Nº PEDIDO").isdigit() else 0,
            "produto": g("PRODUTO"),
            "cupom": g("CUPOM"),
            "valor": valor,
            "comprador": g("COMPRADOR"),
            "meio_pagamento": g("MEIO PAGAMENTO"),
        })
    return records

def process_aportes(rows):
    if not rows: return []
    header = rows[0]
    records = []
    
    TIPO_MAP = {
        "Aporte DD Business": "APORTE_DD",
        "Aporte Agroplay Music": "APORTE_MUSIC",
        "Patrocínio": "PATROCINIO",
        "Repasse Vendas": "REPASSE_VENDAS",
        "Rendimento": "RENDIMENTO",
    }
    
    for row in rows[1:]:
        while len(row) < len(header): row.append("")
        def g(col):
            try: return str(row[header.index(col)]).strip() if col in header else ""
            except: return ""
        
        dt = parse_date(g("DATA"))
        valor = parse_valor(g("VALOR (R$)"))
        if not dt or valor == 0: continue
        
        tipo_label = g("TIPO")
        tipo = TIPO_MAP.get(tipo_label, "PATROCINIO")
        nome = g("NOME")
        
        records.append({
            "data": dt,
            "mes": dt[:7],
            "produto_raw": nome,
            "nome": nome,
            "tipo": tipo,
            "descricao": g("DESCRIÇÃO"),
            "valor": valor,
        })
    return records

def update_html(data):
    html_path = "agp_dashboard.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    data_json = json.dumps(data, ensure_ascii=False)
    
    ds = html.index("const DATA=") + len("const DATA=")
    de = html.index(";\nconst fmt=")
    html = html[:ds] + data_json + html[de:]
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"HTML updated: {len(data['despesas'])} despesas, {len(data['receitas'])} receitas, {len(data['aportes'])} aportes")

def main():
    service = get_service()
    
    print("Reading DESPESAS...")
    desp_rows = read_sheet(service, "DESPESAS!A:Z")
    despesas = process_despesas(desp_rows)
    # Remove permutas
    despesas = [d for d in despesas if d["status"] != "Permuta"]
    print(f"  {len(despesas)} registros")
    
    print("Reading RECEITAS...")
    rec_rows = read_sheet(service, "RECEITAS!A:Z")
    receitas = process_receitas(rec_rows)
    print(f"  {len(receitas)} registros")
    
    print("Reading APORTES...")
    ap_rows = read_sheet(service, "APORTES!A:Z")
    aportes = process_aportes(ap_rows)
    print(f"  {len(aportes)} registros")
    
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
