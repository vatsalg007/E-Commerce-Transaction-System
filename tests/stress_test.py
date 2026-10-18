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


def api(method, path, token=None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.request(method, BASE_URL + path, headers=headers, timeout=60, **kwargs)


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


def checkout(buyer, product_id, quantity, unit_price):
    payload = {
        "items": [{"product_id": product_id, "quantity": quantity}],
        "expected_total": str(unit_price * quantity),
    }
    return api("POST", "/checkout", buyer.token, json=payload).status_code


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


def main():
    run_id = uuid.uuid4().hex[:8]
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    stock_race(admin_token, run_id)
    wallet_race(admin_token, run_id)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()