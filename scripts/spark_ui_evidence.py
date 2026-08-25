from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
import time

INPUT = r"C:\Big Data\orders_huge_mixed_quality.csv"

columns = [
    "order_id", "order_date", "status", "customer_id", "customer_name",
    "customer_phone", "customer_email", "city", "district", "delivery_type",
    "delivery_cost", "payment_method", "payment_status", "payment_amount",
    "currency", "total_amount", "items_json"
]
schema = StructType([StructField(name, StringType(), True) for name in columns])

spark = (
    SparkSession.builder
    .appName("MidtermSparkUIEvidence")
    .master("local[*]")
    .config("spark.sql.adaptive.enabled", "true")
    .config("spark.ui.port", "4040")
    .getOrCreate()
)

try:
    df = (
        spark.read
        .schema(schema)
        .option("header", "true")
        .option("inferSchema", "false")
        .option("multiLine", "false")
        .option("quote", '"')
        .option("escape", '"')
        .csv(INPUT)
    )

    print("Spark UI evidence run started")
    print("Input:", INPUT)
    print("Input partitions:", df.rdd.getNumPartitions())

    sample = df.limit(1_000_000).select("order_id", "status", "currency")
    print("Limited records:", sample.count())
    print("Distinct statuses:", sample.select("status").distinct().count())
    print("Distinct currencies:", sample.select("currency").distinct().count())
    print("Spark UI: http://localhost:4040" )
    print("Keep this process running while taking the screenshot.")
    time.sleep(300)
finally:
    spark.stop()
