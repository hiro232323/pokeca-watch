
import csv
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "price_updates.csv"
PRICES = ROOT / "data" / "prices.json"
HISTORY = ROOT / "data" / "history.json"


def load(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def price(value):
    value = (value or "").replace(",", "").strip()
    return int(value) if value else None


def main():
    if not CSV.exists():
        print("価格データ未登録。既存データは変更しません。")
        return

    history = load(HISTORY, [])
    existing = {
        (r["date"], r["card_id"], r["source"])
        for r in history
    }

    with CSV.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            day = datetime.strptime(
                row["date"], "%Y-%m-%d"
            ).date().isoformat()

            item = {
                "date": day,
                "card_id": row["card_id"].strip(),
                "name": row["name"].strip(),
                "raw_price": price(row["raw_price"]),
                "psa10_price": price(row["psa10_price"]),
                "source": row["source"].strip()
            }

            key = (day, item["card_id"], item["source"])
            if key not in existing:
                history.append(item)
                existing.add(key)

    history.sort(key=lambda x: x["date"])

    latest = {}
    for item in history:
        card_id = item["card_id"]
        if card_id not in latest:
            latest[card_id] = {
                "card_id": card_id,
                "name": item["name"],
                "raw_price": None,
                "psa10_price": None
            }

        for field in ("raw_price", "psa10_price"):
            if item[field] is not None:
                latest[card_id][field] = item[field]

    PRICES.parent.mkdir(parents=True, exist_ok=True)
    PRICES.write_text(
        json.dumps(list(latest.values()),
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    HISTORY.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"更新完了：{len(latest)}銘柄")


if __name__ == "__main__":
    main()
