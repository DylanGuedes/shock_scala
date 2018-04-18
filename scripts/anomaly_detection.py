# encoding=utf8
import os
import sys

from pyspark.sql.types import *
from round_coordinates import load_nodes_from_xml, load_edges_from_xml
from math import sin, cos, sqrt, atan2, radians
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, hour, dayofyear, minute, array, udf, collect_list, explode, mean
from pyspark.sql.types import *
from datetime import datetime
import requests


def minute_mod10(minute):
    return minute % 10


def getDistance(x1,y1,x2,y2):
    return sqrt((x2-x1)**2 + (y2-y1)**2)


def calculate_velocity(item):
    meas1, meas2 = item
    ts1, lat1, lon1 = meas1
    ts2, lat2, lon2 = meas2

    # measure1 must occur first than measure2
    if (ts1 > ts2):
        meas2, meas1 = meas1, meas2
        ts1, lat1, lon1 = meas1
        ts2, lat2, lon2 = meas2
        
    distance = getDistance(float(lat1), float(lon1), float(lat2), float(lon2))
    diff = float(ts2)-float(ts1)
    if (diff > 0):
        return distance/diff
    else:
        return 0


def takeby2(points):
    """
    Example:
    >>> takeby2([1, 2, 3, 4, 5, 6])
    [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]
    """
    a1 = points
    a2 = list(points)
    a1.pop()
    a2.pop(0)
    return list(zip(a1, a2))


def take_edge(item):
    _, lat1, lon1 = item[0]
    _, lat2, lon2 = item[1]
    return [[float(lat1), float(lon1)], [float(lat2), float(lon2)]]


def value_minus_mean(kmh_list, mean_val):
    for i, u in enumerate(kmh_list):
        kmh_list[i] = abs(u - mean_val)
    return kmh_list


def array_mean(values):
    return sum(values)/len(values)


def get_schema():
    return StructType([
        StructField("uuid", StringType(), False),
        StructField("capabilities", StructType([
            StructField("current_location", ArrayType(
                StructType([
                    StructField("lat", DoubleType(), False),
                    StructField("lon", DoubleType(), False),
                    StructField("date", StringType(), False),
                    StructField("nodeID", DoubleType(), False),
                    StructField("tick", StringType(), False)
                ])
            ))
        ]))
    ])

if __name__ == '__main__':
    spark = SparkSession.builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    udfEdgesUnified = udf(takeby2, ArrayType(ArrayType(ArrayType(StringType()))))
    udfCalculateVelocity = udf(calculate_velocity, DoubleType())
    udfGetEdge = udf(take_edge, ArrayType(ArrayType(DoubleType())))
    udfValueMinusMean = udf(value_minus_mean, ArrayType(DoubleType()))
    udfArrayMean = udf(array_mean, DoubleType())

    collector_url = "http://localhost:8000/collector"
    r = requests.post(collector_url + '/resources/data', json={"capabilities": ["current_location"]})
    resources = r.json()["resources"]
    rdd = spark.sparkContext.parallelize(resources)

    df = spark.createDataFrame(resources, get_schema())
    df2 = df.select("uuid", explode(col("capabilities.current_location")).alias("values"))

    df3 = df2.withColumn("nodeID", col("values.nodeID").cast(IntegerType()))
    df4 = df3.withColumn("timestamp", col("values.date").cast(TimestampType()))
    df5 = df4.select("uuid", "timestamp", "values.date", "nodeID", "values.tick", "values.lat", "values.lon")\
            .withColumn("edgeWithTimestamp", array(col("tick"), col("lat"), col("lon")))\
            .select("uuid", "tick", "nodeID", "edgeWithTimestamp", "lat", "lon")\
            .groupBy("uuid")\
            .agg(collect_list(col("edgeWithTimestamp")).alias("edgeWithTimestamp"))\
            .select("uuid", udfEdgesUnified(col("edgeWithTimestamp")).alias("edges_unified"))\
            .select(explode(col("edges_unified")).alias("edge_with_tempo"), "uuid")\
            .withColumn("kmh", udfCalculateVelocity(col("edge_with_tempo")))\
            .withColumn("edge", udfGetEdge(col("edge_with_tempo")))\
            .select("edge", "kmh", "uuid")\
            .groupBy("edge")\
            .agg(mean("kmh").alias("kmhmean"), collect_list("kmh").alias("kmh_list"))\
            .withColumn("valueminusmean", udfValueMinusMean(col("kmh_list"), col("kmhmean")))\
            .withColumn("mad", udfArrayMean(col("valueminusmean")))\
            .select("mad", "edge", "kmhmean")

    df5.show(truncate=False)
    df5.printSchema()