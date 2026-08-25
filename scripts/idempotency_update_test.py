from pymongo import MongoClient
import uuid
client=MongoClient("mongodb://localhost:27017",serverSelectionTimeoutMS=10000)
db=client["midterm_data_pipeline"]
v=db["orders_validated"]
doc=v.find_one({"order_id":{"$nin":[None,""]}},{"_id":0,"order_id":1})
assert doc, "No validated business record found"
oid=doc["order_id"]
before=v.estimated_document_count()
marker="idempotency-test-"+uuid.uuid4().hex
dollar=chr(36)
r1=v.update_one({"order_id":oid},{dollar+"set":{"idempotency_test_marker":marker}},upsert=True)
r2=v.update_one({"order_id":oid},{dollar+"set":{"idempotency_test_marker":marker}},upsert=True)
after_upserts=v.estimated_document_count()
v.update_one({"order_id":oid},{dollar+"unset":{"idempotency_test_marker":""}})
after_cleanup=v.estimated_document_count()
print("test_order_id:",oid)
print("before_count:",before)
print("first_matched:",r1.matched_count)
print("first_modified:",r1.modified_count)
print("first_upserted:",r1.upserted_id is not None)
print("second_matched:",r2.matched_count)
print("second_modified:",r2.modified_count)
print("second_upserted:",r2.upserted_id is not None)
print("after_repeated_upsert_count:",after_upserts)
print("after_cleanup_count:",after_cleanup)
print("no_duplicate_created:",before==after_upserts==after_cleanup)
print("unique_index:","uq_orders_validated_order_id" in v.index_information())

