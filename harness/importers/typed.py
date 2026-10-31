"""Turn human-typed scenario-card messages into tool-calling tasks (private; never committed).

    python -m harness.importers.typed private/review/<file>.csv private/tasks_human/<name>

Each message was written from a card in docs/templates/scenario_cards.md, so the card fixes the call it
should produce. One tool per card family, dates relative to ``written_on``. Card S23 ("last 3 months")
is left out: it has no single date to compare against.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from harness.schema import ExpectedCall, Message, Task

DATE = "YYYY-MM-DD"


def _tool(
    name: str, description: str, props: dict[str, dict[str, Any]], required: list[str]
) -> dict[str, Any]:
    params = {"type": "object", "properties": props, "required": required}
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": params},
    }


S = {"type": "string"}
TOOLS = {
    "schedule_delivery": _tool("schedule_delivery", "Schedule or reschedule delivery of an order.", {
        "order_id": {**S, "description": "Order id, e.g. PQ1234"},
        "delivery_date": {**S, "description": f"Delivery date, {DATE}"},
        "weight_kg": {"type": "number", "description": "Parcel weight in kilograms"}},
        ["order_id", "delivery_date", "weight_kg"]),
    "cancel_order": _tool("cancel_order", "Cancel an order.", {"order_id": {**S, "description": "Order id"}}, ["order_id"]),
    "track_order": _tool("track_order", "Get the status of an order.", {"order_id": {**S, "description": "Order id"}}, ["order_id"]),
    "send_money": _tool("send_money", "Send money to someone.", {
        "recipient": {**S, "description": "Who to pay (name or number)"},
        "amount_inr": {"type": "number", "description": "Amount in rupees"}}, ["recipient", "amount_inr"]),
    "pay_bill": _tool("pay_bill", "Pay a bill.", {
        "biller": {**S, "enum": ["electricity", "mobile"]},
        "amount_inr": {"type": "number", "description": "Amount in rupees"},
        "due_date": {**S, "description": f"Due date, {DATE}"}}, ["biller", "amount_inr", "due_date"]),
    "apply_loan": _tool("apply_loan", "Start a loan application.", {
        "amount_inr": {"type": "number", "description": "Loan amount in rupees"},
        "tenure_months": {"type": "integer", "description": "Loan tenure in months"}}, ["amount_inr", "tenure_months"]),
    "recharge_mobile": _tool("recharge_mobile", "Recharge a prepaid phone.", {
        "phone": {**S, "description": "Phone number"},
        "amount_inr": {"type": "number", "description": "Recharge amount in rupees"}}, ["phone", "amount_inr"]),
    "add_to_cart": _tool("add_to_cart", "Add one item to the cart.", {
        "item": {**S, "description": "Item name"},
        "quantity": {"type": "number", "description": "Quantity"},
        "unit": {**S, "enum": ["kg", "g", "l", "ml", "piece"]}}, ["item", "quantity", "unit"]),
    "book_appointment": _tool("book_appointment", "Book an appointment.", {
        "service": {**S, "enum": ["doctor", "salon", "car_service"]},
        "date": {**S, "description": f"Appointment date, {DATE}"},
        "time": {**S, "description": "Appointment time, 24-hour HH:MM"}}, ["service", "date", "time"]),
    "book_train": _tool("book_train", "Book train tickets.", {
        "from_city": {**S, "description": "Departure city"}, "to_city": {**S, "description": "Destination city"},
        "travel_date": {**S, "description": f"Travel date, {DATE}"},
        "passengers": {"type": "integer", "description": "Number of passengers"}},
        ["from_city", "to_city", "travel_date", "passengers"]),
    "set_reminder": _tool("set_reminder", "Set a reminder.", {
        "text": {**S, "description": "What to remind about"},
        "date": {**S, "description": f"Reminder date, {DATE}"},
        "time": {**S, "description": "Reminder time, 24-hour HH:MM"}}, ["text", "date", "time"]),
    "get_statement": _tool("get_statement", "Download a bank statement for a date range.", {
        "from_date": {**S, "description": f"Start of the statement period, {DATE}"},
        "to_date": {**S, "description": f"End of the statement period, {DATE}"}}, ["from_date", "to_date"]),
    "deposit_money": _tool("deposit_money", "Put money into a deposit.", {
        "amount_inr": {"type": "number", "description": "Amount in rupees"}}, ["amount_inr"]),
    "book_cab": _tool("book_cab", "Book a cab.", {
        "destination": {**S, "description": "Where to go"}, "pickup_date": {**S, "description": f"Pickup date, {DATE}"},
        "pickup_time": {**S, "description": "Pickup time, 24-hour HH:MM"}}, ["destination", "pickup_date", "pickup_time"]),
    "order_product": _tool("order_product", "Order a product.", {
        "item": {**S, "description": "Product"}, "price_inr": {"type": "number", "description": "Price in rupees"},
        "deliver_within_days": {"type": "integer", "description": "Deliver within this many days"}},
        ["item", "price_inr", "deliver_within_days"]),
    "add_fuel": _tool("add_fuel", "Add money to a fuel card.", {
        "amount_inr": {"type": "number", "description": "Amount in rupees"}}, ["amount_inr"]),
}  # fmt: skip


def calls(sid: str, w: date) -> list[tuple[str, dict[str, list[Any]], list[str]]]:
    """(tool, acceptable argument values, free-text arguments) for a card; empty if unsupported."""
    day = lambda n: (w + timedelta(days=n)).isoformat()  # noqa: E731
    mon = day((0 - w.weekday()) % 7 or 7)
    nxt = lambda d: date(w.year + (w.month == 12), w.month % 12 + 1, d).isoformat()  # noqa: E731
    f = ["recipient"]
    spec: dict[str, list[tuple[str, dict[str, list[Any]], list[str]]]] = {
        "S01": [("schedule_delivery", {"order_id": ["PQ1021"], "delivery_date": [day(2)], "weight_kg": [1.5]}, [])],
        "S02": [("schedule_delivery", {"order_id": ["PQ1022"], "delivery_date": [mon], "weight_kg": [2.5]}, [])],
        "S03": [("cancel_order", {"order_id": ["PQ1023"]}, [])],
        "S04": [("send_money", {"amount_inr": [2500]}, f)], "S05": [("send_money", {"amount_inr": [150000]}, f)],
        "S06": [("send_money", {"amount_inr": [375]}, f)],
        "S07": [("pay_bill", {"biller": ["electricity"], "amount_inr": [950], "due_date": [day((2 - w.weekday()) % 7 or 7)]}, [])],
        "S08": [("pay_bill", {"biller": ["mobile"], "amount_inr": [399], "due_date": [day(1)]}, [])],
        "S09": [("apply_loan", {"amount_inr": [500000], "tenure_months": [36]}, [])],
        "S10": [("apply_loan", {"amount_inr": [15000000], "tenure_months": [240]}, [])],
        "S11": [("recharge_mobile", {"amount_inr": [666]}, ["phone"])],
        "S12": [("add_to_cart", {"quantity": [0.5], "unit": ["l"]}, ["item"])],
        "S13": [("add_to_cart", {"quantity": [1.5], "unit": ["kg"]}, ["item"]), ("add_to_cart", {"quantity": [2], "unit": ["piece"]}, ["item"])],
        "S14": [("add_to_cart", {"quantity": [2.5], "unit": ["kg"]}, ["item"]), ("add_to_cart", {"quantity": [750, 0.75], "unit": ["g", "kg"]}, ["item"])],
        "S15": [("book_appointment", {"service": ["doctor"], "date": [mon], "time": ["09:30"]}, [])],
        "S16": [("book_appointment", {"service": ["salon"], "date": [day(1)], "time": ["16:45"]}, [])],
        "S17": [("book_appointment", {"service": ["car_service"], "date": [nxt(3)], "time": ["11:15"]}, [])],
        "S18": [("book_train", {"travel_date": [day(2)], "passengers": [2]}, ["from_city", "to_city"])],
        "S19": [("book_train", {"travel_date": [day((4 - w.weekday()) % 7 or 7)], "passengers": [3]}, ["from_city", "to_city"])],
        "S20": [("set_reminder", {"date": [day(1)], "time": ["19:30"]}, ["text"])],
        "S21": [("set_reminder", {"date": [nxt(28)], "time": ["10:00"]}, ["text"])],
        "S22": [("get_statement", {"from_date": [f"{w.year}-{w.month:02d}-01"], "to_date": [day(-1)]}, [])],
        "S24": [("track_order", {"order_id": ["PQ1024"]}, [])],
        "S25": [("deposit_money", {"amount_inr": [12000]}, [])],
        "S26": [("book_cab", {"pickup_date": [w.isoformat()], "pickup_time": ["23:45"]}, ["destination"])],
        "S27": [("order_product", {"price_inr": [599], "deliver_within_days": [3]}, ["item"])],
        "S28": [("add_fuel", {"amount_inr": [500]}, [])],
    }  # fmt: skip
    return spec.get(sid, [])


def build(csv_path: Path) -> list[Task]:
    out: list[Task] = []
    for row in csv.DictReader(csv_path.open(encoding="utf-8-sig", newline="")):
        text, w = row["utterance"].strip(), date.fromisoformat(row["written_on"])
        wanted = calls(row["id"], w)
        if not text or not wanted:
            continue
        names = list(dict.fromkeys(name for name, _, _ in wanted))
        system = f"Today is {w.strftime('%A')}, {w.day} {w.strftime('%B %Y')}. Use the tools when they fit the request."
        out.append(
            Task(
                id=f"ht:{row['id']}:{row['participant']}", source="human_typed", lang="hinglish",
                pair_id=f"ht:{row['id']}", category="parallel" if len(wanted) > 1 else "simple",
                messages=[Message(role="system", content=system), Message(role="user", content=text)],
                tools=[TOOLS[n] for n in names] + [TOOLS[n] for n in TOOLS if n not in names][:2],
                expected_calls=[ExpectedCall(name=n, arguments=a, free_text=ft) for n, a, ft in wanted],
                ref_date=w, provenance="human-typed from scenario cards; private, consented",
            )
        )  # fmt: skip
    return out


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.importers.typed")
    parser.add_argument("csv", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    tasks = build(args.csv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "human_typed.jsonl").write_text(
        "".join(t.model_dump_json(exclude_none=True) + "\n" for t in tasks), encoding="utf-8"
    )
    print(f"wrote {len(tasks)} tasks to {args.out_dir}/human_typed.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
