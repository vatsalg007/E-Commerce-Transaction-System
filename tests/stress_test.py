"""Concurrency stress test. Run against a live server: python tests/stress_test.py"""
import os
import sys
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from functools import partial

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
BUYER_PASSWORD = "stress-pass-123"
CONCURRENT_BUYERS = 100

failures = []


@dataclass
class Buyer:
    email: str
    token: str
    start_balance: Decimal


def api(method, path, token=None, headers=None, **kwargs):
    merged = {"Authorization": f"Bearer {token}"} if token else {}
    merged.update(headers or {})
    return requests.request(method, BASE_URL + path, headers=merged, timeout=60, **kwargs)


def expect(response, status):
    if response.status_code != status:
        raise RuntimeError(
            f"Unexpected response: {response.request.method} {response.url} "
            f"-> {response.status_code} {response.text}"
        )
    return response.json()


def login(email, password):
    body = expect(api("POST", "/auth/login", json={"email": email, "password": password}), 200)
    return body["access_token"]


def create_buyer(email, balance):
    expect(api("POST", "/auth/register", json={"email": email, "password": BUYER_PASSWORD}), 201)
    token = login(email, BUYER_PASSWORD)
    expect(api("POST", "/wallet/topup", token, json={"amount": str(balance)}), 200)
    return Buyer(email, token, balance)


def create_product(admin_token, name, price, stock):
    payload = {"name": name, "price": str(price), "stock": stock}
    return expect(api("POST", "/products", admin_token, json=payload), 201)["id"]

def place_order(buyer, product_id, quantity, unit_price, key=None):
    payload = {
        "items": [{"product_id": product_id, "quantity": quantity}],
        "expected_total": str(unit_price * quantity),
    }
    headers = {"Idempotency-Key": key or str(uuid.uuid4())}
    return api("POST", "/checkout", buyer.token, headers=headers, json=payload)


def checkout(buyer, product_id, quantity, unit_price):
    return place_order(buyer, product_id, quantity, unit_price).status_code


def get_stock(product_id):
    return expect(api("GET", f"/products/{product_id}"), 200)["stock"]


def get_balance(buyer):
    return Decimal(expect(api("GET", "/auth/me", buyer.token), 200)["wallet_balance"])


def count_orders(buyer):
    return len(expect(api("GET", "/orders", buyer.token), 200))


def run_in_parallel(jobs):
    """Run every job in its own thread; a barrier releases them all at the same moment."""
    barrier = threading.Barrier(len(jobs))

    def run(job):
        barrier.wait()
        return job()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(run, jobs))


def check(label, condition):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


def stock_race(admin_token, run_id):
    stock, price, balance = 10, Decimal("100.00"), Decimal("500.00")
    print(f"\nScenario A: {CONCURRENT_BUYERS} buyers, {stock} units in stock, one unit each")

    product_id = create_product(admin_token, f"Stress A {run_id}", price, stock)
    with ThreadPoolExecutor(max_workers=10) as pool:
        buyers = list(pool.map(
            lambda i: create_buyer(f"stress_{run_id}_a{i}@test.com", balance),
            range(CONCURRENT_BUYERS),
        ))

    statuses = run_in_parallel([partial(checkout, b, product_id, 1, price) for b in buyers])

    counts = Counter(statuses)
    rejected = CONCURRENT_BUYERS - stock
    check(f"exactly {stock} purchases succeeded (got {counts[201]})", counts[201] == stock)
    check(f"the other {rejected} were rejected with 409 (got {counts[409]})", counts[409] == rejected)
    check(f"no other status codes (got {dict(counts)})", set(counts) <= {201, 409})

    final_stock = get_stock(product_id)
    check(f"final stock is 0 (got {final_stock})", final_stock == 0)

    wrong = 0
    for buyer, status in zip(buyers, statuses):
        bought = status == 201
        expected_balance = balance - price if bought else balance
        expected_orders = 1 if bought else 0
        if get_balance(buyer) != expected_balance or count_orders(buyer) != expected_orders:
            wrong += 1
    check(f"every wallet balance and order history is exact ({wrong} wrong)", wrong == 0)


def wallet_race(admin_token, run_id):
    price, balance, affordable = Decimal("100.00"), Decimal("500.00"), 5
    print(f"\nScenario B: one user, {CONCURRENT_BUYERS} simultaneous checkouts, wallet covers {affordable}")

    product_id = create_product(admin_token, f"Stress B {run_id}", price, CONCURRENT_BUYERS)
    buyer = create_buyer(f"stress_{run_id}_b@test.com", balance)

    job = partial(checkout, buyer, product_id, 1, price)
    statuses = run_in_parallel([job] * CONCURRENT_BUYERS)

    counts = Counter(statuses)
    rejected = CONCURRENT_BUYERS - affordable
    check(f"exactly {affordable} purchases succeeded (got {counts[201]})", counts[201] == affordable)
    check(f"the other {rejected} were rejected with 409 (got {counts[409]})", counts[409] == rejected)
    check(f"no other status codes (got {dict(counts)})", set(counts) <= {201, 409})

    final_balance = get_balance(buyer)
    check(f"final wallet balance is exactly 0.00 (got {final_balance})", final_balance == 0)
    final_stock = get_stock(product_id)
    expected_stock = CONCURRENT_BUYERS - affordable
    check(f"stock is {expected_stock}, so rejected checkouts released their stock (got {final_stock})",
          final_stock == expected_stock)
    orders = count_orders(buyer)
    check(f"exactly {affordable} orders exist (got {orders})", orders == affordable)

def is_replay(response):
    return response.headers.get("Idempotent-Replayed") == "true"


def duplicate_race(admin_token, run_id):
    duplicates, price, balance, stock = 20, Decimal("100.00"), Decimal("500.00"), 10
    print(f"\nScenario C: one user, {duplicates} simultaneous submissions with the same Idempotency-Key")

    product_id = create_product(admin_token, f"Stress C {run_id}", price, stock)
    buyer = create_buyer(f"stress_{run_id}_c@test.com", balance)
    key = str(uuid.uuid4())

    job = partial(place_order, buyer, product_id, 1, price, key)
    responses = run_in_parallel([job] * duplicates)

    counts = Counter(r.status_code for r in responses)
    replays = sum(1 for r in responses if is_replay(r))
    check(f"all {duplicates} responses are 201 (got {dict(counts)})", counts[201] == duplicates)
    check(f"exactly 1 request created the order, {duplicates - 1} were replays (replays: {replays})",
          replays == duplicates - 1)

    order_ids = {r.json()["order_id"] for r in responses if r.status_code == 201}
    check(f"all responses point to the same order (got {order_ids})", len(order_ids) == 1)

    final_balance = get_balance(buyer)
    check(f"charged exactly once: balance is {balance - price} (got {final_balance})",
          final_balance == balance - price)
    final_stock = get_stock(product_id)
    check(f"stock reduced exactly once: {stock - 1} (got {final_stock})", final_stock == stock - 1)
    orders = count_orders(buyer)
    check(f"exactly 1 order exists (got {orders})", orders == 1)

    misuse = place_order(buyer, product_id, 2, price, key)
    check(f"same key with a different cart is rejected (422: {misuse.status_code})", misuse.status_code == 422)
    check("balance unchanged after the misuse attempt", get_balance(buyer) == balance - price)


def stored_failure(admin_token, run_id):
    price, start_balance, topup, stock = Decimal("100.00"), Decimal("50.00"), Decimal("500.00"), 10
    print("\nScenario D: a definitive failure is stored under its key")

    product_id = create_product(admin_token, f"Stress D {run_id}", price, stock)
    buyer = create_buyer(f"stress_{run_id}_d@test.com", start_balance)
    key = str(uuid.uuid4())

    first = place_order(buyer, product_id, 1, price, key)
    check(f"first attempt is rejected for low balance (409: {first.status_code})", first.status_code == 409)
    check("the first rejection is not flagged as a replay", not is_replay(first))
    check(f"rejected attempt took no stock (got {get_stock(product_id)})", get_stock(product_id) == stock)

    expect(api("POST", "/wallet/topup", buyer.token, json={"amount": str(topup)}), 200)

    retry = place_order(buyer, product_id, 1, price, key)
    check(f"same key replays the stored 409 even though the wallet now covers it (got {retry.status_code})",
          retry.status_code == 409 and is_replay(retry))
    check("no order was created by the replay", count_orders(buyer) == 0)

    fresh = place_order(buyer, product_id, 1, price)
    check(f"a new key runs the purchase (201: {fresh.status_code})", fresh.status_code == 201)
    expected_balance = start_balance + topup - price
    check(f"balance is exactly {expected_balance} (got {get_balance(buyer)})",
          get_balance(buyer) == expected_balance)
    check(f"stock reduced once: {stock - 1} (got {get_stock(product_id)})", get_stock(product_id) == stock - 1)
    check("exactly 1 order exists", count_orders(buyer) == 1)

SCENARIOS = {
    "A": stock_race,
    "B": wallet_race,
    "C": duplicate_race,
    "D": stored_failure,
}

def main():
    selected = [name.upper() for name in sys.argv[1:]] or list(SCENARIOS)
    unknown = [name for name in selected if name not in SCENARIOS]
    if unknown:
        sys.exit(f"Unknown scenario(s): {', '.join(unknown)}. Choose from: {', '.join(SCENARIOS)}")

    run_id = uuid.uuid4().hex[:8]
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    for name in selected:
        SCENARIOS[name](admin_token, run_id)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()