"""Initialize MongoDB collections and indexes for the UUID benchmark."""

import pymongo

from config.settings import MONGO_URL, MONGO_DB_NAME


def init_mongo() -> None:
    client = pymongo.MongoClient(MONGO_URL)
    db = client[MONGO_DB_NAME]

    for prefix in ("uuid_v4", "uuid_v7"):
        print(f"Setting up {prefix} collections...")

        # Customers collection
        cust_col = db[f"{prefix}.customers"]
        cust_col.create_index("email", unique=True, background=True)
        cust_col.create_index("created_at", background=True)

        # Accounts collection
        acct_col = db[f"{prefix}.accounts"]
        acct_col.create_index("customer_id", background=True)
        acct_col.create_index("opened_at", background=True)
        acct_col.create_index("status", background=True)

    print("MongoDB collections initialized.")
    client.close()


if __name__ == "__main__":
    init_mongo()
