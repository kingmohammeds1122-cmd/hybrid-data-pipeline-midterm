"""PySpark raw loader using the official MongoDB Spark Connector."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, lit, monotonically_increasing_id, struct
from pyspark.sql.types import StringType, StructField, StructType

from config import settings


MONGODB_SPARK_CONNECTOR_PACKAGE = (
    "org.mongodb.spark:mongo-spark-connector_2.12:10.7.0"
)


RAW_CSV_COLUMNS: tuple[str, ...] = (
    "order_id",
    "order_date",
    "status",
    "customer_id",
    "customer_name",
    "customer_phone",
    "customer_email",
    "city",
    "district",
    "delivery_type",
    "delivery_cost",
    "payment_method",
    "payment_status",
    "payment_amount",
    "currency",
    "total_amount",
    "items_json",
)


RAW_CSV_SCHEMA = StructType(
    [
        StructField(column_name, StringType(), True)
        for column_name in RAW_CSV_COLUMNS
    ]
)



def build_collection_uri(collection_name: str) -> str:
    """Build a Connector URI containing database and collection names."""

    return (
        f"{settings.MONGODB_URI.rstrip('/')}/"
        f"{settings.MONGODB_DATABASE}.{collection_name}"
    )



def create_spark_session() -> SparkSession:
    """Create Spark and resolve the official MongoDB Spark Connector."""

    read_uri = build_collection_uri(settings.ORDERS_RAW_COLLECTION)
    write_uri = build_collection_uri(settings.ORDERS_RAW_COLLECTION)

    return (
        SparkSession.builder
        .appName("MidtermDataPipelineSparkRawLoader")
        .master("local[*]")
        .config("spark.sql.adaptive.enabled", "true")
        .config(
            "spark.jars.packages",
            MONGODB_SPARK_CONNECTOR_PACKAGE,
        )
        .config("spark.mongodb.read.connection.uri", read_uri)
        .config("spark.mongodb.write.connection.uri", write_uri)
        .getOrCreate()
    )



def add_raw_metadata(
    dataframe: DataFrame,
    run_id: str,
    source_file: str,
    ingested_at: datetime,
) -> DataFrame:
    """Create the required Raw document contract."""

    raw_record_columns = [
        col(column_name).alias(column_name)
        for column_name in RAW_CSV_COLUMNS
    ]

    return (
        dataframe
        .withColumn(
            "source_row_number",
            monotonically_increasing_id() + 2,
        )
        .withColumn("run_id", lit(run_id))
        .withColumn("source_file", lit(source_file))
        .withColumn("ingested_at", lit(ingested_at.isoformat()))
        .withColumn("engine_used", lit("pyspark"))
        .withColumn("raw_record", struct(*raw_record_columns))
        .select(
            "run_id",
            "source_file",
            "source_row_number",
            "ingested_at",
            "engine_used",
            "raw_record",
        )
    )



def write_with_mongodb_spark_connector(
    dataframe: DataFrame,
) -> None:
    """Write a DataFrame through the official MongoDB Spark Connector."""

    write_uri = build_collection_uri(settings.ORDERS_RAW_COLLECTION)

    (
        dataframe.write
        .format("mongodb")
        .mode("append")
        .option("spark.mongodb.write.connection.uri", write_uri)
        .option("database", settings.MONGODB_DATABASE)
        .option("collection", settings.ORDERS_RAW_COLLECTION)
        .save()
    )



def load_csv_to_raw_with_spark(input_file: Path) -> dict[str, Any]:
    """Read a CSV with Spark and write it with MongoDB Spark Connector."""

    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    if not input_file.is_file():
        raise ValueError(f"Input path is not a regular file: {input_file}")

    run_id = str(uuid4())
    source_file = str(input_file.resolve())
    ingested_at = datetime.now(timezone.utc)
    started_performance = time.perf_counter()
    spark = create_spark_session()

    try:
        dataframe = (
            spark.read
            .schema(RAW_CSV_SCHEMA)
            .option("header", "true")
            .option("inferSchema", "false")
            .option("multiLine", "false")
            .option("quote", '"')
            .option("escape", '"')
            .option("encoding", "UTF-8")
            .csv(str(input_file))
        )

        raw_dataframe = add_raw_metadata(
            dataframe=dataframe,
            run_id=run_id,
            source_file=source_file,
            ingested_at=ingested_at,
        )

        partition_count = raw_dataframe.rdd.getNumPartitions()
        record_count = raw_dataframe.count()
        write_with_mongodb_spark_connector(raw_dataframe)
        elapsed_seconds = time.perf_counter() - started_performance

        return {
            "run_id": run_id,
            "source_file": source_file,
            "engine_used": "pyspark",
            "records_loaded": record_count,
            "partitions_processed": partition_count,
            "batch_size": settings.BATCH_SIZE,
            "source_row_number_strategy": "distributed_monotonic_id",
            "writer": "mongodb_spark_connector",
            "connector_package": MONGODB_SPARK_CONNECTOR_PACKAGE,
            "elapsed_seconds": round(elapsed_seconds, 6),
            "records_per_second": (
                round(record_count / elapsed_seconds, 2)
                if elapsed_seconds > 0
                else 0.0
            ),
        }
    finally:
        spark.stop()



def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Load a CSV into orders_raw using MongoDB Spark Connector."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.SAMPLE_DATA_FILE,
        help="Path to the input CSV file.",
    )
    return parser



def main() -> int:
    """Run the Connector-based PySpark raw loader."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        result = load_csv_to_raw_with_spark(arguments.input)
    except (FileNotFoundError, ValueError, OSError) as error:
        parser.error(str(error))
        return 2

    print("PySpark raw loading with MongoDB Spark Connector completed")
    for key, value in result.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
