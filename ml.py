__author__ = 'adi'
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from pyspark import SparkContext,SparkConf
from pyspark.mllib.feature import HashingTF
from pyspark.mllib.feature import IDF
from pyspark.mllib.clustering import KMeans, KMeansModel

def main(sc):

    stopset = set(stopwords.words('english'))

    tweets = sc.textFile('hdfs:/adi/sample.txt')
    words = tweets.map(lambda word: word.split(" "))
    wordArr = []
    for wArr in words.collect():
        tempArr = []
        for w in wArr:
                if not w in stopset:
                        tempArr.append(w)
        wordArr.append(tempArr)
    # Open a file
   # print wordArr
    #tokens = sc.textFile("hdfs:/adi/tokens1.txt")

    # Load documents (one per line).
    documents = sc.textFile("hdfs:/adi/tokens1.txt").map(lambda line: line.split(" "))
    numDims = 100000
    hashingTF = HashingTF(numDims)
    tf = hashingTF.transform(documents)
    tf.cache()
    idf = IDF().fit(tf)
    tfidf = idf.transform(tf)
    tfidf.count()
    model = KMeans.train(tfidf, 5)
    model.save(sc,"tweetModel1")
    print("Final centers: " + str(model.clusterCenters))
#    print("Total Cost: " + str(model.computeCost(data)))
    sc.stop()


if __name__ == "__main__":
   # Configure Spark
   conf = SparkConf().setAppName("ml").setMaster("spark://10.0.1.90:7077").set("spark.executor.memory", "21000m").set("spark.driver.memory", "1g").set("spark.executor.cores", 4).set("spark.task.cpus",1).set("spark.eventLog.enabled","true").set("spark.eventLog.dir","/home/ubuntu/storage/logs")

   sc = SparkContext(conf=conf)
   # Execute Main functionality
   main(sc)

