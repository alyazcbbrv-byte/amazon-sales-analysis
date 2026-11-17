"""
ETL: Amazon Excel fayllarını oxuyur, təmizləyir və data/processed/ qovluğuna CSV kimi yazır.

İstifadə:
    python src/etl.py                 # data/raw/ qovluğundan oxuyur
    python src/etl.py --raw "C:/yol"  # başqa qovluqdan oxuyur
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

FILES = {
    "sales": "Amazon Database sales.xlsx",
    "city": "Amazon Database City.xlsx",
    "sku": "Amazon Database SKU.xlsx",
    "stock": "Amazon Database stock.xlsx",
}


def _find(raw: Path, name: str) -> Path:
    """Fayl adında boşluq və ya alt xətt ola bilər — hər ikisini yoxla."""
    for candidate in (name, name.replace(" ", "_")):
        p = raw / candidate
        if p.exists():
            return p
    raise FileNotFoundError(f"{name} tapılmadı: {raw}")


def _read_with_header(path: Path, header_first_col: str, sheet=0) -> pd.DataFrame | dict:
    """Başlıq sətrini (ilk sütunu header_first_col olan) tapıb ondan aşağını oxuyur.
    Mənbə fayllarda başlıqdan əvvəl lazımsız sətirlər var."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None, engine="openpyxl")
    frames = raw if isinstance(raw, dict) else {"_": raw}
    out = {}
    for name, df in frames.items():
        idx = df.index[df.iloc[:, 0].astype(str).str.strip() == header_first_col]
        if len(idx) == 0:
            raise ValueError(f"{path.name}/{name}: '{header_first_col}' başlığı tapılmadı")
        h = idx[0]
        body = df.iloc[h + 1 :].copy()
        body.columns = [str(c).strip() for c in df.iloc[h]]
        out[name] = body.reset_index(drop=True)
    return out if isinstance(raw, dict) else out["_"]


def _excel_date(s: pd.Series) -> pd.Series:
    """Excel seriya nömrəsi və ya hazır tarix → date."""
    num = pd.to_numeric(s, errors="coerce")
    as_serial = pd.to_datetime(num, unit="D", origin="1899-12-30", errors="coerce")
    as_date = pd.to_datetime(s.where(num.isna()), errors="coerce")
    return as_serial.fillna(as_date).dt.normalize()


def load_sales(raw: Path) -> pd.DataFrame:
    sheets = _read_with_header(_find(raw, FILES["sales"]), "Tarix", sheet=None)
    df = pd.concat(sheets.values(), ignore_index=True)
    df = df.rename(columns={"Şəhər_İD": "Seher_ID", "Sifaris_İD": "Sifaris_ID", "Satış": "Satis",
                            "Məhsul_kodu": "Mehsul_kodu"})
    df["Tarix"] = _excel_date(df["Tarix"])
    df["Satis"] = pd.to_numeric(df["Satis"], errors="coerce").round(2)
    df["Seher_ID"] = pd.to_numeric(df["Seher_ID"], errors="coerce").astype("Int64")
    df["Sifaris_ID"] = pd.to_numeric(df["Sifaris_ID"], errors="coerce").astype("Int64")
    df["Tip"] = df["Tip"].astype(str).str.strip()
    df["Mehsul_kodu"] = df["Mehsul_kodu"].astype(str).str.strip()
    df = df.dropna(subset=["Tarix", "Satis", "Mehsul_kodu"])
    return df[["Tarix", "Seher_ID", "Sifaris_ID", "Satis", "Tip", "Mehsul_kodu"]]


def load_city(raw: Path) -> pd.DataFrame:
    df = _read_with_header(_find(raw, FILES["city"]), "Ştat_İD")
    df.columns = ["Stat_ID", "Stat", "Seher_ID", "Seher", "lat", "lng"]
    df["Seher_ID"] = pd.to_numeric(df["Seher_ID"], errors="coerce").astype("Int64")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df = df.dropna(subset=["Seher_ID"]).drop_duplicates("Seher_ID")
    df["Seher_Stat"] = df["Seher"].astype(str) + ", " + df["Stat_ID"].astype(str)
    return df


def load_sku(raw: Path) -> pd.DataFrame:
    df = pd.read_excel(_find(raw, FILES["sku"]), header=None, engine="openpyxl")
    df.columns = ["Mehsul_kodu", "Dizayn_No", "Kateqoriya", "Olcu", "Reng"]
    df = df[df["Mehsul_kodu"].notna() & (df["Mehsul_kodu"] != "Məhsul_kodu")]
    df["Mehsul_kodu"] = df["Mehsul_kodu"].astype(str).str.strip()
    df["Kateqoriya"] = df["Kateqoriya"].astype(str).str.strip().str.upper()
    return df.drop_duplicates("Mehsul_kodu")


def load_stock(raw: Path) -> pd.DataFrame:
    sheets = _read_with_header(_find(raw, FILES["stock"]), "Stock", sheet=None)
    df = pd.concat(sheets.values(), ignore_index=True)
    df = df.rename(columns={"Məhsul_kodu": "Mehsul_kodu"})
    df["Tarix"] = _excel_date(df["Tarix"])
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").astype("Int64")
    df["Mehsul_kodu"] = df["Mehsul_kodu"].astype(str).str.strip()
    df = df.dropna(subset=["Tarix", "Stock"])
    df = df[df["Mehsul_kodu"].ne("nan")]
    return df[["Tarix", "Mehsul_kodu", "Stock"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=RAW_DIR, help="Excel fayllarının qovluğu")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "sales": load_sales(args.raw),
        "city": load_city(args.raw),
        "sku": load_sku(args.raw),
        "stock": load_stock(args.raw),
    }
    for name, df in tables.items():
        path = OUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8", date_format="%Y-%m-%d")
        print(f"{name:6s} {len(df):>9,} sətir → {path.relative_to(ROOT)}")

    # Keyfiyyət yoxlaması: əlaqəli cədvəllərdə tapılmayan açarlar
    s, c, k = tables["sales"], tables["city"], tables["sku"]
    miss_city = (~s["Seher_ID"].isin(c["Seher_ID"])).mean()
    miss_sku = (~s["Mehsul_kodu"].isin(k["Mehsul_kodu"])).mean()
    print(f"Şəhəri tapılmayan satışlar: {miss_city:.2%} | SKU-su tapılmayan satışlar: {miss_sku:.2%}")


if __name__ == "__main__":
    main()
