
# Import required libraries
import math
import threading
import logging
import time
import sys
import os
from PIL import Image, ImageTk
import tkinter as tk
from random import randint, shuffle, random, uniform
import numpy as np

# Adjustable globals
numberOfBots = 10
numEquipment = 50
botVisionRadius = 75
botCommunicationRange = 75
botSlowdown = 0.05
maxBotTurnInRads = 0.25
highlightMode = False
startOfCommunicationDelay = 0 # bots start talking after each bot has had X turns
GUI = True
botTimeoutAmount = 5
negativePriority = - (numberOfBots * 10)

# Helper globals
startCoord = [500, 125]  # (Y, X)
endCoord = [225, 650]  # (Y, X)
botStepSize = 10
paused = False
myThread = None
highlightRects = []
listOfBots = []
readyToExit = False
botDrawRadius = 5
batchFileMode = False
environmentName = "green"
outputFileName = "tests_and_results/results.csv"
delayFlag = False


class Bot:
    def __init__(self, botNumber):
        self.pathRGB = np.array([randint(50, 255), randint(50, 255), randint(50, 255), 255]).tolist()
        # self.pathRGB = np.array([255, 50, 150, 255]).tolist()
        self.pathHex = "#" + str(hex(self.pathRGB[0]))[2:] + str(hex(self.pathRGB[1]))[2:] + str(hex(self.pathRGB[2]))[2:]
        self.y = startCoord[0]
        self.x = startCoord[1]
        self.pathHistory = [(self.y, self.x)]
        self.number = botNumber
        self.drawCircle = 0
        self.drawCargo = 0
        self.hasSuccessfulPath = False
        self.isCarryingCargo = False
        self.isHeadingTowardsDest = False
        self.pathHistoryIndex = 0
        self.direction = 2 * math.pi * random()
        self.intersections = [(startCoord[0], startCoord[1])]
        self.recentlySeenBots = list()
        pointGrid[self.y][self.x].append(self.pathRGB)
        self.doneMovingEquipment = False
        self.jobDone = False
        self.betterPathData = None # will have the form (startIndex,  stopIndex, betterPath) betterPath will not include start/stop points
        self.canAcceptPathUpdates = True
        self.timeoutCounter = 0
        self.canCommunicate = True
        self.communicationPriorityDict = dict()

class MyThread(threading.Thread):
    def __init__(self, listOfBots, numEquipment):
        threading.Thread.__init__(self)
        self.paused = False
        self.pause_cond = threading.Condition(threading.Lock())
        self.bots = listOfBots
        self.numEquipmentToMove = numEquipment
        self.numEquipmentAtStart = numEquipment
        self.numEquipmentAtDest = 0
        self.cycles = 0
        self.totalNumCommunications = 0
        self.totalPixelsOfPathChanges = 0


    def run(self):
        global botVisionRadius
        global readyToExit
        global delayFlag
        while True:
            if readyToExit:
                break
            with self.pause_cond:
                while self.paused:
                    self.pause_cond.wait()
                shuffle(self.bots)
                allBotsAreDone = True

                for bot in self.bots:
                    if not bot.jobDone:
                        allBotsAreDone = False
                        if bot.timeoutCounter <= 0:
                            #      ------------------------------
                            #          Search for destination
                            #      ------------------------------

                            if not bot.hasSuccessfulPath:  # Bot is looking for destination
                                # Log current position
                                prevStep = (bot.y, bot.x)

                                # Check if bot can see/move to destination
                                rads, dist = self.getRadsAndDist(bot.y, bot.x, endCoord[0], endCoord[1])
                                if dist <= botStepSize and self.getPathPixels(bot.y, bot.x, rads, dist)[0] == True:
                                    yStep = endCoord[0] - bot.y
                                    xStep = endCoord[1] - bot.x
                                    bot.hasSuccessfulPath = True

                                else:
                                    if dist <= botVisionRadius and self.getPathPixels(bot.y, bot.x, rads, dist)[0] == True:
                                        # Bot can see destination but can't reach it just yet, so it moves towards it
                                        dy = endCoord[0] - bot.y
                                        dx = endCoord[1] - bot.x
                                        bot.direction = math.atan2(dy, dx)
                                        yStep = round(math.sin(bot.direction) * botStepSize)
                                        xStep = round(math.cos(bot.direction) * botStepSize)

                                    else:
                                        yStep, xStep = self.generateNextBotCoordinates(bot)

                                # Check for intersections along new part of path and handle appropriately
                                rads, dist = self.getRadsAndDist(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
                                pixelPath = self.getPathPixels(bot.y, bot.x, rads, dist)
                                bot.pathHistoryIndex += len(pixelPath[1]) -1

                                for i in range(1, len(pixelPath[1])):
                                    self.addBotMetaDataToPoint(bot, pixelPath[1][i])
                                    bot.pathHistory.append(pixelPath[1][i])

                                # Move bot
                                bot.y += yStep
                                bot.x += xStep



                            else:   # Bot has found destination and is transporting cargo

                                #      ---------------------------------------------
                                #          Head to destination to drop off cargo
                                #      ---------------------------------------------

                                # Bot is carrying cargo and is moving towards destination
                                if bot.isHeadingTowardsDest:

                                    # Apply smoothing to bot's path as it moves forward
                                    if bot.canAcceptPathUpdates:
                                        self.applyPathSmoothing(bot, 'forward')

                                    # Go forward through path history
                                    bot.pathHistoryIndex += botStepSize
                                    if bot.pathHistoryIndex >= len(bot.pathHistory):
                                        bot.pathHistoryIndex = len(bot.pathHistory) - 1
                                        bot.hasSuccessfulPath = True
                                        if bot.isCarryingCargo:
                                            self.numEquipmentAtDest += 1
                                        bot.isCarryingCargo = False

                                        bot.isHeadingTowardsDest = False
                                        if bot.doneMovingEquipment:
                                            bot.jobDone = True

                                    if bot.betterPathData is not None and bot.pathHistoryIndex >= bot.betterPathData[1]:
                                        start = bot.betterPathData[0]
                                        stop = bot.betterPathData[1]
                                        path = bot.betterPathData[2]
                                        for i in range(start, stop):
                                            self.removeBotMetaDataFromPoint(bot, bot.pathHistory[i])

                                        if bot.pathHistory[bot.pathHistoryIndex][0] == endCoord[0] and \
                                            bot.pathHistory[bot.pathHistoryIndex][1]  == endCoord[1]:
                                            bot.pathHistoryIndex = len(path) - 1
                                        else:
                                            bot.pathHistoryIndex = bot.pathHistoryIndex - (stop - start) + len(path)

                                        bot.pathHistory = bot.pathHistory[:start] + path + bot.pathHistory[stop:]

                                        bot.canAcceptPathUpdates = True
                                        bot.betterPathData = None
                                        for i in range(len(path)):
                                            self.addBotMetaDataToPoint(bot, path[i])

                                    try:
                                        bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                        bot.x = bot.pathHistory[bot.pathHistoryIndex][1]
                                    except IndexError:
                                        pass


                                #      --------------------------------------------
                                #          Head back to start to get more cargo
                                #      --------------------------------------------

                                # Bot is not carrying cargo and is heading back to start
                                else:
                                    # Apply smoothing to bot's path as it moves backwards
                                    if bot.canAcceptPathUpdates:
                                        self.applyPathSmoothing(bot, 'backwards')

                                    # Go backwards through path history
                                    bot.pathHistoryIndex -= botStepSize

                                    # Bot is at start coordinates
                                    if bot.pathHistoryIndex < 0:
                                        bot.pathHistoryIndex = 0
                                        bot.isHeadingTowardsDest = True
                                        if bot.pathHistory[len(bot.pathHistory)-1][0] == endCoord[0] and \
                                            bot.pathHistory[len(bot.pathHistory) - 1][1] == endCoord[1]:
                                            bot.hasSuccessfulPath = True
                                        if self.numEquipmentAtStart > 0:
                                            self.numEquipmentAtStart -= 1
                                            bot.isCarryingCargo = True
                                        else:
                                            bot.doneMovingEquipment = True

                                    if bot.betterPathData is not None and bot.pathHistoryIndex <= bot.betterPathData[0]:
                                        start = bot.betterPathData[0]
                                        stop = bot.betterPathData[1]
                                        path = bot.betterPathData[2]
                                        for i in range(start, stop):
                                            self.removeBotMetaDataFromPoint(bot, bot.pathHistory[i])
                                        bot.pathHistory = bot.pathHistory[:start] + path + bot.pathHistory[stop:]
                                        bot.canAcceptPathUpdates = True
                                        bot.betterPathData = None
                                        for i in range(len(bot.pathHistory)):
                                            self.addBotMetaDataToPoint(bot, bot.pathHistory[i])


                                    bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                    bot.x = bot.pathHistory[bot.pathHistoryIndex][1]


                            #      -----------------------------------
                            #          Communicate with other bots
                            #      -----------------------------------

                            if self.cycles > startOfCommunicationDelay:
                                priorityBot = self.getPriorityCommPartner(bot)
                                if priorityBot is not None:
                                    self.compareAndUpdatePaths(bot, priorityBot)

                        else:
                            bot.timeoutCounter -= 1


                #      --------------------------
                #          End of cycle logic
                #      --------------------------

                self.incrementPriorities()

                if allBotsAreDone:
                    self.logTestData()
                    closeGracefully()

                self.cycles += 1

                # Slow down bots (simulate movement and help visual analysis)
                time.sleep(botSlowdown)

    def logTestData(self):
        # Set up thread logging
        logging.basicConfig(filename=outputFileName,
                            format='%(message)s',
                            filemode='a',
                            level=logging.DEBUG)
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        if os.path.exists(outputFileName) and os.stat(outputFileName).st_size == 0:
            logger.info(
                # PARAMETERS
                "numBots," +
                "numEquipment," +
                "visionRadius," +
                "commRange," +
                "commStartDelay," +
                "commTimeoutLength," +
                "negativePriority," +
                "enviroName," +

                # RESULTS

                "cycles," +
                "avgPathLength"
            )

        # Get avg path length for all bots
        total = 0
        for bot in self.bots:
            total += len(bot.pathHistory)
        avgPathLength = int(total / len(self.bots))


        logger.info(
            # PARAMETERS
            str(numberOfBots) + "," +
            str(numEquipment) + "," +
            str(botVisionRadius) + "," +
            str(botCommunicationRange) + "," +
            str(startOfCommunicationDelay) + "," +
            str(botTimeoutAmount) + "," +
            str(negativePriority) + "," +
            str(environmentName) + "," +

            # RESULTS

            str(self.cycles) + "," +
            str(avgPathLength)

        )
        logging.shutdown()

    def pause(self):
        self.paused = True
        self.pause_cond.acquire()

    def resume(self):
        self.paused = False
        self.pause_cond.notify_all()
        self.pause_cond.release()

    def calcDist(self, y1, x1, y2, x2):
        return math.sqrt((y1-y2)**2 + (x1-x2)**2)

    def generateNextBotCoordinates(self, bot):
        failedAttempts = 0
        while True:
            maxRadians = maxBotTurnInRads + (failedAttempts * 0.05)  if 0.5 * (failedAttempts * 0.25) < 2* math.pi else 2* math.pi
            newDirection = bot.direction + uniform(-maxRadians, maxRadians)
            yStep = round(math.sin(newDirection) * botStepSize)
            xStep = round(math.cos(newDirection) * botStepSize)
            rads, dist = self.getRadsAndDist(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
            botPathData = self.getPathPixels(bot.y, bot.x, rads, dist)
            if botPathData[0] == True:
                bot.direction = newDirection
                break
            failedAttempts += 1
        return yStep, xStep

    # Function implemented with the help of https://www.geeksforgeeks.org/mid-point-circle-drawing-algorithm/
    # Gets the pixel coordinates of the perimeter of a circle. Much faster than looping with degrees/radians
    # ******************* RETURNS COORDINATES IN X,Y FORMAT ***************************
    def getPerimeterCoords(self, xOffset, yOffset):
        pointsAlongCircle = [(xOffset, yOffset - botVisionRadius),
                             (xOffset + botVisionRadius, yOffset),
                             (xOffset, yOffset + botVisionRadius),
                             (xOffset - botVisionRadius, yOffset)]
        x = botVisionRadius
        y = 0
        P = 1 - botVisionRadius
        while x > y:
            y += 1
            if P <= 0:
                P = P + 2 * y + 1
            else:
                x -= 1
                P = P + 2 * y - 2 * x + 1
            if x < y:
                break

            pointsAlongCircle.append((x + xOffset, y + yOffset))
            pointsAlongCircle.append((-x + xOffset, y + yOffset))
            pointsAlongCircle.append((x + xOffset, -y + yOffset))
            pointsAlongCircle.append((-x + xOffset, -y + yOffset))

            if x != y:
                pointsAlongCircle.append((y + xOffset, x + yOffset))
                pointsAlongCircle.append((-y + xOffset, x + yOffset))
                pointsAlongCircle.append((y + xOffset, -x + yOffset))
                pointsAlongCircle.append((-y + xOffset, -x + yOffset))
        return pointsAlongCircle

    # Function implemented with the help of http://www.roguebasin.com/index.php?title=Bresenham%27s_Line_Algorithm
    # Checks each point in a line to ensure a bot doesn't "jump" over an illegal area
    def getPathPixels(self, y, x, rads, distance):
        currentY, currentX = y, x
        futureY, futureX = self.getCoordsFromPointAndAngle(currentY, currentX, rads, distance)

        # If line is steeper than 45 degrees, then swap x and y to rotate the line
        lineIsSteep = abs(futureY - currentY) > abs(futureX - currentX)
        if lineIsSteep:
            currentX, currentY = currentY, currentX
            futureX, futureY = futureY, futureX

        # If end point is to the left of start point, then swap start and end points
        startEndSwapped = False
        if currentX > futureX:
            currentX, futureX = futureX, currentX
            currentY, futureY = futureY, currentY
            startEndSwapped = True

        # Calculate differences, error, and yStep
        dx = futureX - currentX
        dy = futureY - currentY
        e = int(dx / 2.0)
        if currentY < futureY:
            yStep = 1
        else:
            yStep = -1

        y = currentY
        coordList = []
        foundImpassableTerrain = False
        for x in range(currentX, futureX + 1):
            coords = (x, y)
            if lineIsSteep:
                coords = (y, x)
            if coords[1] < 0 or coords[1] >= height or coords[0] < 0 or coords[0] >= width:
                return [False, coordList]
            coordList.append((coords[1], coords[0]))
            if impassableTerrainArray[coords[1]][coords[0]] == 1:
                foundImpassableTerrain = True
            e -= abs(dy)
            if e < 0:
                y += yStep
                e += dx
        if startEndSwapped:
            coordList.reverse()

        if foundImpassableTerrain:
            return [False, coordList]
        return [True, coordList]

    def compareAndUpdatePaths(self, bot, otherBot):
        # EXCHANGE PATH INFO HERE
        # if you hit an intersection, update both paths appropriately)
        dataTransferred = False
        if bot.hasSuccessfulPath and otherBot.hasSuccessfulPath:

            # Both bots have a successful path, so find intersections and optimize both paths

            # Find the intersections
            sharedIntersections = set()
            for point in bot.intersections:
                if otherBot.pathRGB in pointGrid[point[0]][point[1]]:
                    sharedIntersections.add(point)

            for point in otherBot.intersections:
                if bot.pathRGB in pointGrid[point[0]][point[1]]:
                    sharedIntersections.add(point)

            botIndices = []
            otherBotIndices = []

            for point in sharedIntersections:
                try:
                    botIndex = bot.pathHistory.index(point)
                    otherBotIndex = otherBot.pathHistory.index(point)
                except:
                    continue

                botIndices.append((botIndex, point))
                otherBotIndices.append((otherBotIndex, point))

            botIndices = sorted(botIndices, key=lambda tup: tup[0])
            otherBotIndices = sorted(otherBotIndices, key=lambda tup: tup[0])
            dataTransferred = False
            totalDataTransferred = 0

            for i in range(len(botIndices) - 2, -1, -1):

                # Make sure we're looking at the exact same point
                if botIndices[i][1] != otherBotIndices[i][1] or botIndices[i+1][1] != otherBotIndices[i+1][1]:
                    return

                botStartIndex = botIndices[i][0]
                botEndIndex = botIndices[i + 1][0]
                otherBotStartIndex = otherBotIndices[i][0]
                otherBotEndIndex = otherBotIndices[i + 1][0]
                lengthOfBotPath = botEndIndex - botStartIndex
                lengthOfOtherBotPath = otherBotEndIndex - otherBotStartIndex

                # Don't adjust this section of paths for either bot if both sections are almost the same length (saves processing time)
                if abs(lengthOfBotPath - lengthOfOtherBotPath) < 10:
                    continue

                botIsInSection = False
                if botStartIndex < bot.pathHistoryIndex < botEndIndex:
                    botIsInSection = True

                otherBotIsInSection = False
                if otherBotStartIndex < otherBot.pathHistoryIndex < otherBotEndIndex:
                    otherBotIsInSection = True

                botHasShorterSection = False
                otherBotHasShorterSection = False
                if lengthOfBotPath < lengthOfOtherBotPath:
                    botHasShorterSection = True
                else:
                    otherBotHasShorterSection = True

                # bot has shorter section, so improve otherBot's section
                if botHasShorterSection:
                    if otherBot.canAcceptPathUpdates:
                        # otherBot is in the current section, but bot has shorter section
                        if otherBotIsInSection:
                            otherBot.betterPathData = (otherBotStartIndex, otherBotEndIndex, bot.pathHistory[botStartIndex : botEndIndex])
                            otherBot.canAcceptPathUpdates = False

                        # other bot is not in section, but bot has shorter section
                        else:
                            if highlightMode:
                                # Colour path being removed all white to see steps
                                self.pause()
                                for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                                    numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = [255, 255, 255]
                                self.pause()
                                # for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                                #     numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = pointGrid[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]][0]


                            for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                                self.removeBotMetaDataFromPoint(otherBot, otherBot.pathHistory[i])

                            otherBot.pathHistory = otherBot.pathHistory[:otherBotStartIndex] + bot.pathHistory[botStartIndex:botEndIndex] + otherBot.pathHistory[otherBotEndIndex:]

                            if otherBot.pathHistoryIndex >= otherBotEndIndex:
                                otherBot.pathHistoryIndex = otherBot.pathHistoryIndex - lengthOfOtherBotPath + lengthOfBotPath

                                findIndex = otherBot.pathHistory.index((otherBot.pathHistory[otherBot.pathHistoryIndex][0], otherBot.pathHistory[otherBot.pathHistoryIndex][1]))

                            highlightRects.append((otherBot.pathHistory[otherBot.pathHistoryIndex][0],
                                                   otherBot.pathHistory[otherBot.pathHistoryIndex][1]))

                            for i in range(botStartIndex + 1, botEndIndex):
                                self.addBotMetaDataToPoint(otherBot, bot.pathHistory[i])

                            if highlightMode:
                                self.pause()

                # otherBot has shorter section, so improve bot's section
                else:
                    if bot.canAcceptPathUpdates:
                        # bot is in the current section, but otherBot has shorter section
                        if botIsInSection:
                            bot.betterPathData = (botStartIndex, botEndIndex, otherBot.pathHistory[otherBotStartIndex : otherBotEndIndex])
                            bot.canAcceptPathUpdates = False
                        # bot is not in section, but otherBot has shorter section
                        else:
                            if highlightMode:
                                # Colour path being removed all white to see steps
                                self.pause()
                                for i in range(botStartIndex + 1, botEndIndex):
                                    numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = [255, 255, 255]
                                self.pause()
                                # for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                                #     numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = pointGrid[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]][0]

                            for i in range(botStartIndex + 1, botEndIndex):
                                self.removeBotMetaDataFromPoint(bot, bot.pathHistory[i])

                            bot.pathHistory = bot.pathHistory[:botStartIndex] + otherBot.pathHistory[otherBotStartIndex:otherBotEndIndex] + bot.pathHistory[botEndIndex:]

                            if bot.pathHistoryIndex >= botEndIndex:
                                bot.pathHistoryIndex = bot.pathHistoryIndex - lengthOfBotPath + lengthOfOtherBotPath

                                findIndex = bot.pathHistory.index((bot.pathHistory[bot.pathHistoryIndex][0],
                                                                        bot.pathHistory[bot.pathHistoryIndex][1]))

                            highlightRects.append((bot.pathHistory[bot.pathHistoryIndex][0],
                                                   bot.pathHistory[bot.pathHistoryIndex][1]))

                            for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                                self.addBotMetaDataToPoint(bot, otherBot.pathHistory[i])

                            if highlightMode:
                                self.pause()

                # End of iteration, clear section specific things, e.g. highlightRects list
                dataTransferred = True
                totalDataTransferred += min(lengthOfBotPath, lengthOfOtherBotPath)
                highlightRects.clear()

        if bot.hasSuccessfulPath != otherBot.hasSuccessfulPath:
            if bot.hasSuccessfulPath and not otherBot.hasSuccessfulPath:
                # Bot gives path to OtherBot
                helper = bot
                helpee = otherBot
            if not bot.hasSuccessfulPath and otherBot.hasSuccessfulPath:
                # OtherBot gives path to Bot
                helper = otherBot
                helpee = bot

            rads, dist = self.getRadsAndDist(helper.y, helper.x, helpee.y, helpee.x)
            pixelPath = self.getPathPixels(helper.y, helper.x, rads, dist)
            if pixelPath[0] == True:
                for i in range(len(helpee.pathHistory)):
                    self.removeBotMetaDataFromPoint(helpee, helpee.pathHistory[i])

                yBefore = helpee.pathHistory[helpee.pathHistoryIndex][0]
                xBefore = helpee.pathHistory[helpee.pathHistoryIndex][1]


                helpee.pathHistory = helper.pathHistory[:helper.pathHistoryIndex] + \
                                     pixelPath[1][:len(pixelPath[1])-1] + \
                                     pixelPath[1][::-1] + \
                                     helper.pathHistory[helper.pathHistoryIndex+1:]

                helpee.pathHistoryIndex = helpee.pathHistory.index((helpee.y, helpee.x))

                for i in range(len(helpee.pathHistory)):
                    self.addBotMetaDataToPoint(helpee, helpee.pathHistory[i])



                helpee.y = helpee.pathHistory[helpee.pathHistoryIndex][0]
                helpee.x = helpee.pathHistory[helpee.pathHistoryIndex][1]

                yAfter = helpee.pathHistory[helpee.pathHistoryIndex][0]
                xAfter = helpee.pathHistory[helpee.pathHistoryIndex][1]


                self.applyPathSmoothing(helpee, 'forward')
                self.applyPathSmoothing(helpee, 'backward')

                helpee.hasSuccessfulPath = True
                helpee.isCarryingCargo = False
                helpee.isHeadingTowardsDest = False

                dataTransferred = True


        if dataTransferred:
            bot.timeoutCounter = botTimeoutAmount
            otherBot.timeoutCounter = botTimeoutAmount
            self.totalNumCommunications += 1


        # Two safeguard checks to ensure that bot status "successful path" status get's updated if needed after changes
        if bot.pathHistory[len(bot.pathHistory) - 1][0] == endCoord[0] and \
                bot.pathHistory[len(bot.pathHistory) - 1][1] == endCoord[1]:
            bot.hasSuccessfulPath = True
        if otherBot.pathHistory[len(otherBot.pathHistory) - 1][0] == endCoord[0] and \
                otherBot.pathHistory[len(otherBot.pathHistory) - 1][1] == endCoord[1]:
            otherBot.hasSuccessfulPath = True

    def removeBotMetaDataFromPoint(self, bot, point):
        pointData = pointGrid[point[0]][point[1]]
        try:
            pointData.remove(bot.pathRGB)
            bot.intersections.remove(point)
        except ValueError:
            pass
        numpyEnvironment[point[0]][point[1]] = pointData[0][:3] if len(pointData) != 0 else [0, 0, 0]

    def addBotMetaDataToPoint(self, bot, point):
        pointData = pointGrid[point[0]][point[1]]
        if bot.pathRGB not in pointData:
            pointData.append(bot.pathRGB)
        if len(pointData) != 1:
            bot.intersections.append(point)
        numpyEnvironment[point[0]][point[1]] = pointData[0][:3]

    def applyPathSmoothing(self, bot, direction):
        forward = True if direction == 'forward' else False
        perimeterCoords = self.getPerimeterCoords(bot.x, bot.y)
        pointsFoundInHistory = []
        for point in perimeterCoords:
            xPoint = 0 if point[0] < 0 else width - 1 if point[0] > width - 1 else point[0]
            yPoint = 0 if point[1] < 0 else height - 1 if point[1] > height - 1 else point[1]

            # Disregard point if it's not a valid destination
            if impassableTerrainArray[yPoint][xPoint] == 1:
                continue

            # Check if perimeter point is same colour as bot's colour
            if bot.pathRGB in pointGrid[yPoint][xPoint]:

                # Make sure the path to the point being examined is valid and not blocked
                rads, dist = self.getRadsAndDist(bot.y, bot.x, yPoint, xPoint)
                pixelPathData = self.getPathPixels(bot.y, bot.x, rads, dist)
                if pixelPathData[0] == False:
                    continue

                if forward:
                    # Make sure point isn't in the wrong direction (avoids looking through entire path history for no reason)
                    backTrackIndex = int(bot.pathHistoryIndex - (1.5 * botStepSize)) if bot.pathHistoryIndex > (
                                1.5 * botStepSize) else 0
                    if point in bot.pathHistory[backTrackIndex:bot.pathHistoryIndex]:
                        continue
                    # Look through path history in the appropriate direction and add perimeter points and their indices (in bot's path history) to a temporary list
                    for i in range(bot.pathHistoryIndex, len(bot.pathHistory)):
                        if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                            pointsFoundInHistory.append((i, yPoint, xPoint))
                else:
                    backTrackIndex = int(bot.pathHistoryIndex + (1.5 * botStepSize)) if bot.pathHistoryIndex + (
                                1.5 * botStepSize) < len(bot.pathHistory) else len(bot.pathHistory) - 1
                    if point in bot.pathHistory[bot.pathHistoryIndex:backTrackIndex + 1]:
                        continue

                    # Look through path history in the appropriate direction and add perimeter points and their indices (in bot's path history) to a temporary list
                    for i in range(bot.pathHistoryIndex, -1, -1):
                        if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                            pointsFoundInHistory.append((i, yPoint, xPoint))

        if len(pointsFoundInHistory) != 0:
            # Determine which point provides the best shortcut (the farthest index)
            if forward:
                pointsFoundInHistory.sort(key=lambda x: x[0], reverse=True)
                bestPoint = pointsFoundInHistory[0]
                rads, dist = self.getRadsAndDist(bot.y, bot.x, bestPoint[1], bestPoint[2])
                newPathPixelData = self.getPathPixels(bot.y, bot.x, rads, dist)
            else:
                pointsFoundInHistory.sort(key=lambda x: x[0])
                bestPoint = pointsFoundInHistory[0]
                rads, dist = self.getRadsAndDist(bestPoint[1], bestPoint[2], bot.y, bot.x)
                newPathPixelData = self.getPathPixels(bestPoint[1], bestPoint[2], rads, dist)

            start, stop, step = (bot.pathHistoryIndex, bestPoint[0] + 1, 1) if forward else (bot.pathHistoryIndex, bestPoint[0] - 1, -1)
            for i in range(start, stop, step):
                self.removeBotMetaDataFromPoint(bot, bot.pathHistory[i])

            # Check for intersections along updated path section and handle appropriately
            for i in range(len(newPathPixelData[1])):
                self.addBotMetaDataToPoint(bot, newPathPixelData[1][i])

            sectionStart, sectionStop = (bot.pathHistoryIndex, bestPoint[0] + 1) if forward else (bestPoint[0], bot.pathHistoryIndex + 1)
            bot.pathHistory = bot.pathHistory[:sectionStart] + newPathPixelData[1] + bot.pathHistory[sectionStop:]

            if not forward:
                bot.pathHistoryIndex = bestPoint[0] + len(newPathPixelData[1]) - 1

        else:  # no shortcut found, heading towards destination
            if forward:
                stopIndex = bot.pathHistoryIndex + botStepSize if bot.pathHistoryIndex + botStepSize <= len(bot.pathHistory) else len(bot.pathHistory)
                for i in range(bot.pathHistoryIndex + 1, stopIndex):
                    self.addBotMetaDataToPoint(bot, bot.pathHistory[i])
            else:
                stopIndex = bot.pathHistoryIndex - botStepSize if bot.pathHistoryIndex - botStepSize > -1 else -1
                for i in range(bot.pathHistoryIndex - 1, stopIndex, -1):
                    self.addBotMetaDataToPoint(bot, bot.pathHistory[i])

    def getRadiansOfPoints(self, y1, x1, y2, x2):
        return math.atan2(y2-y1, x2-x1)

    def getCoordsFromPointAndAngle(self, y, x, rads, distance):
        yPoint = y + round(math.sin(rads) * distance)
        xPoint = x + round(math.cos(rads) * distance)
        return yPoint, xPoint

    def getRadsAndDist(self, y1, x1, y2, x2):
        return self.getRadiansOfPoints(y1, x1, y2, x2), self.calcDist(y1, x1, y2, x2)

    def botsCanCommunicate(self, bot, otherBot):
        rads, dist = self.getRadsAndDist(bot.y, bot.x, otherBot.y, otherBot.x)
        if dist > botCommunicationRange:
            return False
        pathBetweenBots = self.getPathPixels(bot.y, bot.x, rads, dist)

        # Simulate degradation of signal strength over rough terrain
        interference = 0
        for point in pathBetweenBots[1]:
            if impassableTerrainArray[point[0]][point[1]] == 0:
                interference += 1
            else:
                interference += 2

            if interference >= botCommunicationRange:
                return False
        return True

    def getPriorityCommPartner(self, bot):
        candidates = []
        for b in self.bots:
            if bot.pathRGB != b.pathRGB and self.botsCanCommunicate(bot, b):
                candidates.append(b)

        if len(candidates) == 0:
            return None

        newBots = []
        notNewBots = []

        for candidate in candidates:
            if tuple(candidate.pathRGB) in bot.communicationPriorityDict.keys():
                notNewBots.append((bot.communicationPriorityDict[tuple(candidate.pathRGB)], candidate))
            else:
                newBots.append(candidate)

        priorityBot = None
        if len(newBots) == 0:
            highestPriority = 0
            for oldBot in notNewBots:
                if oldBot[0] > highestPriority:
                    highestPriority = oldBot[0]
                    priorityBot = oldBot[1]
        else:
            shuffle(newBots)
            priorityBot = newBots[0]

        if priorityBot is not None:
            bot.communicationPriorityDict[tuple(priorityBot.pathRGB)] = negativePriority
            priorityBot.communicationPriorityDict[tuple(bot.pathRGB)] = negativePriority

        return priorityBot

    def incrementPriorities(self):
        for bot in self.bots:
            for key in bot.communicationPriorityDict.keys():
                bot.communicationPriorityDict[key] = bot.communicationPriorityDict[key] + 1


def drawStartEndLines(w):
    half = 15
    start1 = w.create_line(startCoord[1] - half, startCoord[0] - half, startCoord[1] + half, startCoord[0] + half, fill='#00FF00', width=4)
    start2 = w.create_line(startCoord[1] + half, startCoord[0] - half, startCoord[1] - half, startCoord[0] + half, fill='#00FF00', width=4)
    end1 = w.create_line(endCoord[1] - half, endCoord[0] - half, endCoord[1] + half, endCoord[0] + half, fill='#e6194B', width=4)
    end2 = w.create_line(endCoord[1] + half, endCoord[0] - half, endCoord[1] - half, endCoord[0] + half, fill='#e6194B', width=4)
    return [start1, start2, end1, end2]

def pauseButton():
    global paused
    global highlightMode
    if highlightMode:
        paused = False
        myThread.resume()
    else:
        if not paused:
            paused = True
            myThread.pause()
        else:
            paused = False
            myThread.resume()
def slowerButton():
    global botSlowdown
    botSlowdown *= 1.25
def fasterButton():
    global botSlowdown
    botSlowdown /= 1.25

def closeGracefully():
    global readyToExit
    readyToExit = True
    if GUI:
        root.destroy()
    print("Program terminated.")

# Main function
if __name__ == "__main__":
    if len(sys.argv) != 1:
        if sys.argv[1] == 'noGUI':
            GUI = False
            botSlowdown = 0
        numberOfBots = int(sys.argv[2])
        numEquipment = int(sys.argv[3])
        botVisionRadius = int(sys.argv[4])
        botCommunicationRange = int(sys.argv[5])
        startOfCommunicationDelay = int(sys.argv[6])
        botTimeoutAmount = int(sys.argv[7])
        negativePriority = int(sys.argv[8])
        environmentName = sys.argv[9]
        outputFileName = sys.argv[10]

    if environmentName == "black750":
        environmentPath = "environments/black750.png"

    elif environmentName == "black1500":
        environmentPath = "environments/black1500.png"
        startCoord = [350, 181]  # (Y, X)
        endCoord = [148, 1334]  # (Y, X)

    elif environmentName == "blue":
        environmentPath = "environments/environment2.png"
        startCoord = [350, 181]  # (Y, X)
        endCoord = [148, 1334]  # (Y, X)

    elif environmentName == "breaker1":
        environmentPath = "environments/breaker1.PNG"

    else:
        environmentPath = "environments/environment1.png"

    # Start program timer
    programStartTime = time.time()

    # Initialize PIL images, data, and tools
    originalBG = Image.open(environmentPath)
    numpyEnvironment = np.array(originalBG)[...,:3]
    height, width = numpyEnvironment.shape[0], numpyEnvironment.shape[1]
    originalBG.close()

    pointGrid = []
    for row in range(height):
        tempRow = []
        for col in range(width):
            tempRow.append([])
        pointGrid.append(tempRow)

    print("Program launching...")
    if GUI:
        # Initialize tkinter tools and open window
        root = tk.Tk()
        root.title("Swarm Pathfinding")
        root.geometry("+0+5")
        root.protocol('WM_DELETE_WINDOW', closeGracefully)
        window = tk.Canvas(root, width=width, height=height)
        backgroundImage = ImageTk.PhotoImage(Image.fromarray(numpyEnvironment))
        topFrame = tk.Frame(root)
        topFrame.focus_set()
        topFrame.pack(side=tk.TOP, expand=True)
        bottomFrame = tk.Frame(root)
        bottomFrame.pack(side=tk.BOTTOM)
        slowButton = tk.Button(root, text="Slow down", width=10, height=1, command=slowerButton)
        pauseButton = tk.Button(root, text='Pause/Unpause', width=15, height=1, command=pauseButton)
        fastButton = tk.Button(root, text="Speed up", width=10, height=1, command=fasterButton)
        slowButton.pack(in_=bottomFrame, side=tk.LEFT)
        pauseButton.pack(in_=bottomFrame, side=tk.LEFT)
        fastButton.pack(in_=bottomFrame, side=tk.LEFT)
        window.create_image(0, 0, anchor=tk.N + tk.W, image=backgroundImage)
    else:
        botSlowdown = 0

    # Make a matrix for calculating where bots can and can't go (0 is free space, 1 is impassable terrain)
    impassableTerrainArray = []
    for row in range(height):
        tempRow = []
        for col in range(width):
            pixel = numpyEnvironment[row][col]
            if pixel[0] == 0 and pixel[1] == 0 and pixel[2] == 0:
                tempRow.append(0)
            else:
                tempRow.append(1)
        impassableTerrainArray.append(tempRow)

    # Spawn bots and launch bots' thread
    for index in range(numberOfBots):
        bot = Bot(index)
        listOfBots.append(bot)
    myThread = MyThread(listOfBots, numEquipment)
    myThread.start()

    if GUI:
        startEndLines = drawStartEndLines(window)
        while True:
            if readyToExit:
                break

            else:
                window.delete("all")
                workingImage = ImageTk.PhotoImage(Image.fromarray(numpyEnvironment))
                window.create_image(0, 0, anchor=tk.N + tk.W, image=workingImage)
                for line in startEndLines:
                    window.delete(line)
                startEndLines = drawStartEndLines(window)

                for bot in listOfBots:
                    window.delete(bot.drawCircle)
                    bot.drawCircle = window.create_rectangle(bot.x - botDrawRadius, bot.y - botDrawRadius, bot.x + botDrawRadius,
                                                             bot.y + botDrawRadius, fill=bot.pathHex, outline=bot.pathHex)
                    if bot.isCarryingCargo:
                        window.delete(bot.drawCargo)
                        bot.drawCargo = window.create_rectangle(bot.x - botDrawRadius - 2, bot.y - (1.5 * botDrawRadius),
                                                                bot.x + botDrawRadius + 2, bot.y - (0.5 * botDrawRadius),
                                                                fill='gray78', outline='gray78')

                for c in highlightRects:
                    window.create_rectangle(c[1] - botDrawRadius, c[0] - botDrawRadius, c[1] + botDrawRadius,
                                            c[0] + botDrawRadius, fill='white', outline='white')

                window.pack()
                window.update()

    print("Total program runtime = {0:.2f}".format(time.time() - programStartTime))