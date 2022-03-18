from flask import Flask, request
from time import time
import redis
import os

app = Flask(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT")
REDIS_DB = os.environ.get("REDIS_DB")


def numberOfPrimesUpTo(limit):
    count = 0
    for i in range(int(limit) + 1):
        if i > 1:
            isPrime = True
            for j in range(2, i):
                if i % j == 0:
                    isPrime = False
                    break
            if isPrime:
                count += 1
    return count


def storeResult(primeLimit, primesFound, elapsedTime):
    if not REDIS_HOST:
        print("Redis not configured.")
        return
    r = redis.Redis(REDIS_HOST, REDIS_PORT, REDIS_DB)
    r.set(primeLimit, f"{primesFound} primes in {elapsedTime} seconds")


@app.route("/primes")
def default():
    start = time()
    limit = request.args.get("limit")
    primes = numberOfPrimesUpTo(limit)
    elapsed = round(time() - start, 2)
    storeResult(limit, primes, elapsed)
    return f"Found {primes} primes in {elapsed} seconds.\n"


if __name__ == "__main__":
    # Enable debug to prevent generic 500 error while testing.
    app.run(host="0.0.0.0", port=80, debug=True)
