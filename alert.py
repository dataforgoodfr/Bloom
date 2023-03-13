import csv
from time import sleep


with open('bloom_scrp.csv') as file_object:

    read_object = csv.reader(file_object)

    for row in read_object:
        sleep(600)
        if ((row == row[-1]) and (next(file_object)!=-1)):
            #Send slack notification

 