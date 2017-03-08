#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import math
import copy
import numpy as np

from PyQt5.QtCore import QObject
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal

from sources.TextPreprocessing import writeStringToFile
from sources.classification.KNN import getResponse
from sources.classification.NaiveBayes import *
from sources.classification.clsf_util import *


class ClassificationCalculatorSignals(QObject):
    PrintInfo = pyqtSignal(str)
    Finished = pyqtSignal()
    UpdateProgressBar = pyqtSignal(int)


class ClassificationCalculator(QThread):

    METHOD_NAIVE_BAYES = 1
    METHOD_ROCCHIO = 2
    METHOD_KNN = 3

    def __init__(self, input_dir, output_dir, morph, configurations):
        super().__init__()
        self.input_dir = input_dir
        if(len(self.input_dir)>0 and self.input_dir[-1] != '/'):
            self.input_dir = self.input_dir + '/'
        self.output_dir = output_dir
        self.morph = morph
        self.configurations = configurations
        self.texts = []
        self.categories = dict()
        self.signals = ClassificationCalculatorSignals()
        self.method = ClassificationCalculator.METHOD_NAIVE_BAYES
        self.need_preprocessing = False

    def setMethod(self, method_name, arg_need_preprocessing):
        self.method = method_name
        self.need_preprocessing = arg_need_preprocessing

    def run(self):
        self.signals.UpdateProgressBar.emit(0)

        if self.method == ClassificationCalculator.METHOD_NAIVE_BAYES:
            self.classification_naive_bayes(self.need_preprocessing)

        if self.method == ClassificationCalculator.METHOD_ROCCHIO:
            self.classification_rocchio(self.need_preprocessing)

        if self.method == ClassificationCalculator.METHOD_KNN:
            self.classification_knn(self.need_preprocessing)

        self.signals.UpdateProgressBar.emit(100)
        self.signals.PrintInfo.emit('Рассчеты закончены!')
        self.signals.Finished.emit()

    # Алгоритм наивного Байеса
    def classification_naive_bayes(self, needPreprocessing):

        ##############PARAMS###################
        output_dir = self.output_dir + 'nb_out/'
        input_dir = self.input_dir
        ###############ALGO##################

        self.signals.PrintInfo.emit("Алгоритм наивного Байеса")
        # Классификация
        fdata, fclass, split = makeFileList(input_dir)
        self.signals.UpdateProgressBar.emit(10)

        trainingSet = fdata[:split]
        trainingClass = fclass[:split]
        testSet = fdata[split:]
        test_fnames = makeFileList(input_dir, fread=False)[0][split:]
        self.signals.UpdateProgressBar.emit(20)
        vocab = {}
        word_counts = defaultdict(dict)
        priors = dict.fromkeys(set(trainingClass), 0.)
        for cl in priors.keys():
            priors[cl] = trainingClass.count(cl)
        docs = []

        self.signals.UpdateProgressBar.emit(30)

        for i in range(len(trainingSet)):
            counts = count_words(trainingSet[i])
            cl = trainingClass[i]
            for word, count in counts.items():
                if word not in vocab:
                    vocab[word] = 0.0
                if word not in word_counts[cl]:
                    word_counts[cl][word] = 0.0
                vocab[word] += count
                word_counts[cl][word] += count
        self.signals.UpdateProgressBar.emit(40)
        scores = {}
        V = len(vocab)
        for i in range(len(testSet)):
            scores[test_fnames[i]] = []
            counts = count_words(testSet[i])
            Lc = sum(word_counts[cl].values())
            for cl in priors.keys():
                prior_cl = math.log10(priors[cl] / sum(priors.values()))
                log_prob = 0.0
                for w, cnt in counts.items():
                    Wic = word_counts[cl].get(w, 0.0)
                    log_prob += math.log10((Wic + 1) / (V + Lc))
                    #            if not w in vocab:
                    #                continue
                    #
                    #            p_word = vocab[w] / sum(vocab.values())
                    #            p_w_given = word_counts[cl].get(w, 0.0) / sum(word_counts[cl].values())
                    #
                    #            if p_w_given > 0:
                    #                log_prob += math.log(cnt * p_w_given / p_word)
                scores[test_fnames[i]].append([cl, round((log_prob + prior_cl), 3)])
        self.signals.UpdateProgressBar.emit(60)
        self.signals.PrintInfo.emit("Выходные файлы:")
        out_dir = self.output_dir + 'nb_out/'
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        self.signals.PrintInfo.emit(out_dir + 'Словарь всех.csv')
        dictToCsv(vocab, output_dir + 'Словарь всех.csv')
        self.signals.PrintInfo.emit(out_dir + 'Вероятности документов.csv')
        dictToCsv(scores, output_dir + 'Вероятности документов.csv')
        self.signals.PrintInfo.emit(out_dir + 'Словарь по классам.csv')
        dictToCsv(word_counts, output_dir + 'Словарь по классам.csv')

    # Алгоритм Рочио
    def classification_rocchio(self, needPreprocessing):

        def findCentroid(nparray):
            return (np.sum(nparray, axis=0) / len(nparray))

        ##############PARAMS###################
        output_dir = self.output_dir + 'roc_out/'
        input_dir = self.input_dir
        sep = ";"
        eol = "\n"
        ###############ALGO##################

        fdata, fclass, split = makeFileList(input_dir)
        tfidf, uniq_words = makeTFIDF(fdata[:split], fdata[split:])
        class_titles = set(fclass)

        combiSet = addClassToTFIDF(copy.deepcopy(tfidf), fclass)
        trainSet = combiSet[:split]
        testSet = combiSet[split:]
        self.signals.UpdateProgressBar.emit(20)
        centroids = []
        for cl in class_titles:
            cl_array = []
            for i in range(len(trainSet)):
                if fclass[i] == cl:
                    cl_array.append(trainSet[i][:-1])
            centroids.append(findCentroid(np.array(cl_array)).round(3).tolist())

        centroids = addClassToTFIDF(centroids, list(class_titles))
        log_centr = "центроиды" + eol + sep.join(uniq_words) + eol
        for row in centroids:
            log_centr += sep.join(map(str, row)) + eol
        self.signals.UpdateProgressBar.emit(40)
        self.signals.PrintInfo.emit("Алгоритм Роккио")
        log_main = "Расстояние до центроидов" + eol
        predictions = []
        for doc in testSet:
            neighbors, dist = getNeighbors(centroids, testSet[0], len(centroids))
            log_main += str(doc) + eol + sep.join([x[0][-1] for x in dist]) + eol + sep.join(
                map(str, [x[1] for x in dist])) + eol
            self.signals.PrintInfo.emit('> результат =' + repr(dist[0][0][-1]) + ', на самом деле=' + repr(doc[-1]))
            predictions.append(dist[0][0][-1])
        accuracy = getAccuracy(testSet, predictions)
        self.signals.PrintInfo.emit('Точность: ' + repr(accuracy) + '%')
        self.signals.UpdateProgressBar.emit(60)
        ###############LOGS##################
        log_tfidf = sep.join(uniq_words) + eol
        split_names = makeFileList(input_dir, fread=False)[0]
        for i in range(len(combiSet)):
            row = combiSet[i]
            log_tfidf += sep.join(map(str, row)) + sep + split_names[i] + eol

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.signals.PrintInfo.emit('Выходные файлы:')

        self.signals.UpdateProgressBar.emit(80)
        self.signals.PrintInfo.emit(output_dir + 'output_Rocchio.csv')
        writeStringToFile2(log_main, output_dir + 'output_Rocchio.csv')
        self.signals.PrintInfo.emit(output_dir + 'Rocchio_centroids.csv')
        writeStringToFile2(log_centr, output_dir + 'Rocchio_centroids.csv')
        self.signals.PrintInfo.emit(output_dir + 'tfidf_matrix.csv')
        writeStringToFile2(log_tfidf, output_dir + 'tfidf_matrix.csv')

    # Алгоритм KNN
    def classification_knn(self, needPreprocessing):

        ##############PARAMS###################
        output_dir = self.output_dir + 'knn_out/'
        input_dir = self.input_dir
        sep = ";"
        eol = "\n"
        k = self.configurations.get('classification_knn_k')
        ###############ALGO##################

        fdata, fclass, split = makeFileList(input_dir)
        tfidf, uniq_words = makeTFIDF(fdata[:split], fdata[split:])
        self.signals.UpdateProgressBar.emit(20)
        trainingSet = addClassToTFIDF(tfidf[:split], fclass[:split])
        testSet = addClassToTFIDF(tfidf[split:], fclass[split:])
        self.signals.UpdateProgressBar.emit(30)

        self.signals.PrintInfo.emit("Алгоритм KNN")
        predictions = []
        log_neighbors = "Соседи и расстояния до них:" + eol
        log_votes = "Голоса соседей:" + eol
        for x in range(len(testSet)):
            neighbors, dist = getNeighbors(trainingSet, testSet[x], k)
            result = getResponse(neighbors)
            log_neighbors += "Документ:;" + str(testSet[x]) + eol
            for p in dist:
                log_neighbors += sep.join(map(str, p)) + eol
            log_votes += "Документ:;" + str(testSet[x]) + eol + str(result).strip("[]") + eol
            predictions.append(result[0][0])
            self.signals.PrintInfo.emit('> результат =' + repr(result[0][0]) + ', на самом деле=' + repr(testSet[x][-1]))
        accuracy = getAccuracy(testSet, predictions)
        self.signals.PrintInfo.emit('Точность: ' + repr(accuracy) + '%')
        self.signals.UpdateProgressBar.emit(50)
        ###############LOGS##################
        log_tfidf = sep.join(uniq_words) + eol
        combiSet = trainingSet + testSet
        split_names = makeFileList(input_dir, fread=False)[0]
        for i in range(len(combiSet)):
            row = combiSet[i]
            log_tfidf += sep.join(map(str, row)) + sep + split_names[i] + eol
        self.signals.UpdateProgressBar.emit(70)
        self.signals.PrintInfo.emit("Выходные файлы:")

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.signals.PrintInfo.emit(output_dir + 'tfidf_matrix.csv')
        writeStringToFile(log_tfidf, output_dir + 'tfidf_matrix.csv')

        self.signals.PrintInfo.emit(output_dir + 'Соседи.csv')
        writeStringToFile(log_neighbors, output_dir + 'Соседи.csv')

        self.signals.PrintInfo.emit(output_dir + 'Голоса.csv')
        writeStringToFile(log_votes, output_dir + 'Голоса.csv')


