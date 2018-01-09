// Package: --packages org.mongodb.spark:mongo-spark-connector_2.11:2.2.0

import com.mongodb.spark._
import com.mongodb.spark.config._
import org.apache.spark.sql.SparkSession

object InterSCity {
  def loadDatabaseConfig(spark: SparkSession) {
    val readConfig = ReadConfig(Map("collection" -> "sensor_values",
      "spark.mongodb.input.uri" -> "mongodb://data-collector-mongo:27017",
      "spark.mongodb.output.uri" -> "mongodb://data-collector-mongo:27017",
      "spark.mongodb.input.database" -> "data_collector_development"))

    val rdd = MongoSpark.load(spark, readConfig)
    println("RDD =>", rdd)
  }
}
