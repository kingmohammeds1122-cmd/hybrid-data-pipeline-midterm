"""MongoDB database and collection setup for the ELT pipeline."""

from __future__ import annotations

import argparse

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from config import settings


VALIDATED_COLLECTION_VALIDATOR: dict = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "order_id",
            "quality_status",
        ],
        "properties": {
            "order_id": {
                "bsonType": "string",
                "description": "Stable business key and required field.",
            },
            "quality_status": {
                "enum": ["valid", "corrected"],
                "description": "Only usable records can enter validated.",
            },
        },
    }
}


def create_mongodb_client() -> MongoClient:
    """Create a MongoDB client using the central project settings."""

    return MongoClient(
        settings.MONGODB_URI,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        serverSelectionTimeoutMS=(
            settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS
        ),
    )


def ensure_collection(
    database: Database,
    collection_name: str,
) -> Collection:
    """Create a collection if it does not already exist."""

    existing_collections = set(database.list_collection_names())

    if collection_name not in existing_collections:
        database.create_collection(collection_name)

    return database[collection_name]


def configure_validated_collection(
    database: Database,
) -> Collection:
    """Create or update validation and the stable business-key index."""

    collection_name = settings.ORDERS_VALIDATED_COLLECTION
    existing_collections = set(database.list_collection_names())

    if collection_name not in existing_collections:
        database.create_collection(
            collection_name,
            validator=VALIDATED_COLLECTION_VALIDATOR,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        database.command(
            {
                "collMod": collection_name,
                "validator": VALIDATED_COLLECTION_VALIDATOR,
                "validationLevel": "strict",
                "validationAction": "error",
            }
        )

    collection = database[collection_name]
    collection.create_index(
        [(settings.ORDER_BUSINESS_KEY, ASCENDING)],
        name="uq_orders_validated_order_id",
        unique=True,
    )
    return collection


def setup_database() -> dict[str, object]:
    """Configure the required collections and return a setup summary."""

    client = create_mongodb_client()

    try:
        client.admin.command("ping")
        database = client[settings.MONGODB_DATABASE]

        raw_collection = ensure_collection(
            database,
            settings.ORDERS_RAW_COLLECTION,
        )
        validated_collection = configure_validated_collection(database)
        quarantine_collection = ensure_collection(
            database,
            settings.ORDERS_QUARANTINE_COLLECTION,
        )

        return {
            "database": settings.MONGODB_DATABASE,
            "collections": {
                settings.ORDERS_RAW_COLLECTION: {
                    "validator": False,
                    "unique_index_on_order_id": False,
                    "document_count": raw_collection.count_documents({}),
                },
                settings.ORDERS_VALIDATED_COLLECTION: {
                    "validator": True,
                    "unique_index_on_order_id": True,
                    "document_count": validated_collection.count_documents({}),
                },
                settings.ORDERS_QUARANTINE_COLLECTION: {
                    "validator": False,
                    "unique_index_on_order_id": False,
                    "document_count": quarantine_collection.count_documents({}),
                },
            },
        }
    finally:
        client.close()


def main() -> int:
    """Run MongoDB setup and print a verifiable summary."""

    parser = argparse.ArgumentParser(
        description="Set up the MongoDB collections for the ELT pipeline."
    )
    parser.parse_args()

    try:
        summary = setup_database()
    except Exception as error:
        parser.error(f"MongoDB setup failed: {error}")
        return 2

    print("MongoDB setup completed successfully")
    print(f"Database: {summary['database']}")

    collections = summary["collections"]
    for collection_name, details in collections.items():
        print(f"Collection: {collection_name}")
        print(f"  Validator: {details['validator']}")
        print(
            "  Unique index on order_id: "
            f"{details['unique_index_on_order_id']}"
        )
        print(f"  Existing documents: {details['document_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
