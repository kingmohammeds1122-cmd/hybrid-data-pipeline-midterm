from pymongo import MongoClient
run_id="d99b6635-6877-4263-9b17-ff522a49fb48"
c=MongoClient("mongodb://localhost:27017",serverSelectionTimeoutMS=5000)
d=c["midterm_data_pipeline"]
raw=d["orders_raw"].count_documents({})
v=d["orders_validated"].count_documents({})
q=d["orders_quarantine"].count_documents({})
a=d["quarantine_reprocessing_audit"].count_documents({"run_id":run_id})
print("orders_raw:",raw)
print("orders_validated:",v)
print("orders_quarantine:",q)
print("audit_for_run:",a)
print("conservation:",raw==v+q)
print("unique_index:","uq_orders_validated_order_id" in d["orders_validated"].index_information())
