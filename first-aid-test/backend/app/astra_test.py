import requests
import json
from config import (
    ASTRA_DB_API_ENDPOINT,
    ASTRA_DB_KEYSPACE,
    ASTRA_DB_COLLECTION,
    ASTRA_DB_APPLICATION_TOKEN
)

BASE = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{ASTRA_DB_KEYSPACE}"
HEADERS = {
    "Content-Type": "application/json",
    "x-cassandra-token": ASTRA_DB_APPLICATION_TOKEN
}

# 1) Upsert (insert a small document)
doc = {"document": {"_id": "test1", "text": "This is a test first-aid guide snippet."}}
url_upsert = f"{BASE}/collections/{ASTRA_DB_COLLECTION}"
resp = requests.post(url_upsert, headers=HEADERS, data=json.dumps(doc))
print("Upsert:", resp.status_code, resp.text)

# 2) Fetch by ID to confirm
url_get = f"{BASE}/collections/{ASTRA_DB_COLLECTION}/test1"
resp = requests.get(url_get, headers=HEADERS)
print("Get:", resp.status_code, resp.text)
