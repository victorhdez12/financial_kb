from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd


def read_any(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == '.csv':
        return pd.read_csv(path)
    if ext in {'.xlsx', '.xls'}:
        return pd.read_excel(path)
    if ext == '.parquet':
        return pd.read_parquet(path)
    raise ValueError(f'Unsupported file: {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    inp = Path(args.input)
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)

    files = [p for p in inp.rglob('*') if p.is_file() and p.suffix.lower() in {'.csv','.xlsx','.xls','.parquet'}]
    if not files:
        raise SystemExit('No tabular files found.')

    for path in files:
        df = read_any(path)
        target = outdir / f'{path.stem}.parquet'
        df.to_parquet(target, index=False)
        print(f'{path.name}: {len(df):,} rows, {len(df.columns)} cols -> {target}')

if __name__ == '__main__':
    main()
