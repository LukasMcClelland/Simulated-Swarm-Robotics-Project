#TODO
# -look into if object attribute (foo.bar) lookups are actually super slow ! (33% slower)
# -try out using numpy array for basically all GUI stuff and then update everything each frame. seems to fast enough
# -maybe try implementing more functions that can use NUMBA to get better speeds

# Import required libraries
import math
import threading
import logging
import time
from PIL import Image, ImageTk
import tkinter as tk
from random import randint, shuffle, random, uniform
import numpy as np
# from numba import jit

# Adjustable globals
numEquipment = 50
startCoord = [500, 125]  # (Y, X)
endCoord = [225, 650]  # (Y, X)
numberOfBots = 10
botVisionRadius = 100
botStepSize = 10
botSlowdown = 0.01
numberOfDraws = 0
botDrawRadius = 5
maxBotTurnInRads = 0.25
highlightMode = False
startOfCommunicationDelay = 250 # bots start talking after each bot has moved 500 times
GUI = True
botTimeoutAmount = 10

# Helper globals
paused = False
myThread = None
numRounds = 0
workingBG = None
circles = []
listOfBots = []
readyToExit = False


class Bot:
    def __init__(self, botNumber):
        self.pathRGB = np.array([randint(50, 255), randint(50, 255), randint(50, 255), 255]).tolist()
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
        self.shouldMove = True
        self.doneMovingEquipment = False
        self.jobDone = False
        self.betterPathData = None # will have the form (startIndex,  stopIndex, betterPath) betterPath will not include start/stop points
        self.canAcceptPathUpdates = True
        self.timeoutCounter = 0
        self.canCommunicate = True
        self.communicationPriorityList = list()

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

    def run(self):
        global numRounds
        global botVisionRadius
        global readyToExit
        while True:
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
                                distanceToDestination = math.sqrt((endCoord[0] - bot.y) ** 2 + (endCoord[1] - bot.x) ** 2)
                                if distanceToDestination <= botStepSize:
                                    yStep = endCoord[0] - bot.y
                                    xStep = endCoord[1] - bot.x
                                    bot.hasSuccessfulPath = True
                                    if self.numEquipmentAtDest == self.numEquipmentToMove:
                                        bot.jobDone = True

                                else:
                                    if distanceToDestination <= botVisionRadius and len(
                                            self.getMovePixels(bot.y, bot.x, endCoord[0], endCoord[1])) != 0:
                                        # Bot can see destination but can't reach it just yet, so it moves towards it
                                        dy = endCoord[0] - bot.y
                                        dx = endCoord[1] - bot.x
                                        bot.direction = math.atan2(dy, dx)
                                        yStep = round(math.sin(bot.direction) * botStepSize)
                                        xStep = round(math.cos(bot.direction) * botStepSize)

                                    else:
                                        yStep, xStep = self.generateNextBotCoordinates(bot)

                                # Check for intersections along new part of path and handle appropriately
                                pixelPath = self.getMovePixels(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
                                bot.pathHistoryIndex += len(pixelPath) -1

                                for i in range(1, len(pixelPath)):
                                    self.addBotMetaDataToPoint(bot, pixelPath[i])
                                    bot.pathHistory.append(pixelPath[i])

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
                                        bot.pathHistory = bot.pathHistory[:start] + path + bot.pathHistory[stop:]
                                        bot.pathHistoryIndex = (stop - start) - len(path)
                                        bot.canAcceptPathUpdates = True
                                        bot.betterPathData = None
                                        for i in range(len(path)):
                                            self.addBotMetaDataToPoint(bot, path[i])

                                    bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                    bot.x = bot.pathHistory[bot.pathHistoryIndex][1]


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
                                        for i in range(len(path)):
                                            self.addBotMetaDataToPoint(bot, path[i])


                                    bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                    bot.x = bot.pathHistory[bot.pathHistoryIndex][1]

                            #      -----------------------------------
                            #          Communicate with other bots
                            #      -----------------------------------
                            # TODO maybe write a function that returns a list of bots that CAN be communicated with
                            #  -this can handle the 'wireless signal strength simulation' idea, and can handle the
                            #   'sensor/angle' thing as discussed. Do the simulations, return one bot where communication is
                            #   successful and it has the highest priority
                            if self.cycles > startOfCommunicationDelay:
                                for otherBot in listOfBots:
                                    if not bot.pathRGB == otherBot.pathRGB:  # If other bot is not same bot
                                        if (bot.x - otherBot.x) ** 2 + (
                                                bot.y - otherBot.y) ** 2 < botVisionRadius ** 2:  # If other bot within vision range
                                            if otherBot.pathRGB not in bot.recentlySeenBots:
                                                bot.recentlySeenBots.append(otherBot.pathRGB)
                                                otherBot.recentlySeenBots.append(bot.pathRGB)
                                                self.compareAndUpdatePaths(bot, otherBot)

                                        else:  # Other bot is out of range, so make sure it's removed from recently seen list
                                            # TODO maybe add a counter so that bots don't go in, go out, go in, go out, etc every turn
                                            # something like a "if we've seen each other in the last 10 moves or so"
                                            try:
                                                bot.recentlySeenBots.remove(otherBot.pathRGB)
                                            except ValueError:
                                                pass

                                            try:
                                                otherBot.recentlySeenBots.remove(bot.pathRGB)
                                            except ValueError:
                                                pass

                                # Sanity check. Remove before production
                                # for i in range(len(bot.pathHistory)-1):
                                #     p1 = bot.pathHistory[i]
                                #     p2 = bot.pathHistory[i+1]
                                #     if abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) > 2:
                                #         logger.info("##################################################################################")
                                #         self.pause()
                        else:
                            bot.timeoutCounter -= 1

                #      --------------------------
                #          End of cycle logic
                #      --------------------------

                if allBotsAreDone:
                    logger.info("JOB DONE. Number of cycles: " + str(self.cycles))
                    readyToExit = True
                    exit()
                self.cycles += 1

                # Slow down bots (simulate movement and help for visual analysis)
                time.sleep(botSlowdown)

    def pause(self):
        self.paused = True
        self.pause_cond.acquire()

    def resume(self):
        self.paused = False
        self.pause_cond.notify_all()
        self.pause_cond.release()

    def generateNextBotCoordinates(self, bot):
        failedAttempts = 0
        while True:
            maxRadians = maxBotTurnInRads + (failedAttempts * 0.05)  if 0.5 * (failedAttempts * 0.25) < 2* math.pi else 2* math.pi
            newDirection = bot.direction + uniform(-maxRadians, maxRadians)
            yStep = round(math.sin(newDirection) * botStepSize)
            xStep = round(math.cos(newDirection) * botStepSize)
            rads = self.getRadiansOfPoints(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
            botPathData = self.getPathPixels(bot.y, bot.x, rads, botStepSize)
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
            if (0 > y >= height) or (0 > futureX >= width):
                return (False, coordList)
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
            return (False, coordList)
        return (True, coordList)


    def compareAndUpdatePaths(self, bot, otherBot):
        # EXCHANGE PATH INFO HERE
        # if you hit an intersection, update both paths appropriately)
        if not bot.hasSuccessfulPath and not otherBot.hasSuccessfulPath:
            # TODO exchange info between bots if one bot does not know of a successful path
            return

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
                logger.info("POINT COMPARISON ERROR!")
                logger.info("bot points:      " + str(botIndices[i]) + " " + str(botIndices[i + 1]))
                logger.info("otherBot points: " + str(otherBotIndices[i]) + " " + str(otherBotIndices[i + 1]))

                # TODO
                # TODO  It's possible that index is NOT finding the correct index of the point (duplicate points)
                # TODO  Print off all indices of each of the above 4 points and see if this is the cause, if not? FUCK IT bug stays in

                # self.pause()
                continue

            # circles.append(botIndices[i][1])
            # circles.append(otherBotIndices[i][1])

            # logger.info("PAIRS: \nBot 1 is from " + str(bot1Indices[i]) + " to " + str(bot1Indices[i+1]) + ". \nBot 2 is from " + str(bot2Indices[i]) + " to " + str(bot2Indices[i+1]) + ".")
            botStartIndex = botIndices[i][0]
            botEndIndex = botIndices[i + 1][0]
            otherBotStartIndex = otherBotIndices[i][0]
            otherBotEndIndex = otherBotIndices[i + 1][0]
            lengthOfBotPath = botEndIndex - botStartIndex
            lengthOfOtherBotPath = otherBotEndIndex - otherBotStartIndex

            # Don't adjust this section of paths for either bot if both sections are almost the same length (saves processing time)
            if abs(lengthOfBotPath - lengthOfOtherBotPath) < 10:
                continue

            logger.info("Currently examining these bot points:      " + str(botIndices[i]) + " " + str(botIndices[i+1]))
            logger.info("Currently examining these otherBot points: " + str(otherBotIndices[i]) + " " + str(otherBotIndices[i+1]))

            logger.info("\nbotStartIndex            " + str(botStartIndex) +
                        "\nbotEndIndex              " + str(botEndIndex) +
                        "\notherBotStartIndex       " + str(otherBotStartIndex) +
                        "\notherBotEndIndex         " + str(otherBotEndIndex) +
                        "\nlengthOfBotPath          " + str(lengthOfBotPath) +
                        "\nlengthOfOtherBotPath     " + str(lengthOfOtherBotPath) +
                        "\nlen(bot.pathHistory)     " + str(len(bot.pathHistory)) +
                        "\nlen(otherBot.pathHistory)" + str(len(otherBot.pathHistory)))

            botIsInSection = False
            if botStartIndex < bot.pathHistoryIndex < botEndIndex:
                logger.info("bot pathHistoryIndex in between " + str(botStartIndex) + " and " + str(botEndIndex) + "\nBot is in between above intersections")
                botIsInSection = True

            otherBotIsInSection = False
            if otherBotStartIndex < otherBot.pathHistoryIndex < otherBotEndIndex:
                logger.info("otherBot pathHistoryIndex in between " + str(otherBotStartIndex) + " and " + str(otherBotEndIndex) + "\nOtherBot is in between above intersections")
                otherBotIsInSection = True

            botHasShorterSection = False
            otherBotHasShorterSection = False
            if lengthOfBotPath < lengthOfOtherBotPath:
                logger.info("Just compared section lengths. Bot has shorter section")
                botHasShorterSection = True
            else:
                logger.info("Just compared section lengths. OtherBot has shorter section")
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

                        logger.info("In logic for botHasShortSection AND otherBotIsInSection is False")
                        logger.info("Safely removing points in otherBot's pathHistory. Starting at index (incl) " + str(otherBotStartIndex + 1) +
                                    ". Stopping at index (excl) " + str(otherBotEndIndex))

                        if highlightMode:
                            # Colour path being removed all white to see steps
                            for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                                numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = [255, 255, 255, 255]
                            self.pause()
                            # for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                            #     numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = pointGrid[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]][0]


                        for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                            self.removeBotMetaDataFromPoint(otherBot, otherBot.pathHistory[i])


                        logger.info("Changing otherBots pathHistory:" +
                                    "\n 1st chunk is otherBot.pathHistory from start up to index (excl) " + str(otherBotStartIndex) +
                                    "\n 2nd chunk is bot.pathHistory from index " + str(botStartIndex) + " (incl) up to index " + str(botEndIndex) + " (excl)" +
                                    "\n 3rd chunk is otherBot.pathHistory from index " + str(otherBotEndIndex) + " (incl) to end of otherBot.pathHistory")
                        logger.info("OtherBots coords based on history and index before HISTORY CHANGE change: (y= " + str(
                            otherBot.pathHistory[otherBot.pathHistoryIndex][0]) + ", x= " + str(
                            otherBot.pathHistory[otherBot.pathHistoryIndex][1]) + ")")
                        logger.info(
                            "OtherBots otherBot.y and other bot.x before HISTORY change: (" + str(otherBot.y) + ", " + str(
                                otherBot.x) + ")")
                        otherBot.pathHistory = otherBot.pathHistory[:otherBotStartIndex] + bot.pathHistory[botStartIndex:botEndIndex] + otherBot.pathHistory[otherBotEndIndex:]

                        if otherBot.pathHistoryIndex >= otherBotEndIndex:
                            logger.info("OtherBot is currently past section being edited, so it's index must be changed.")
                            logger.info("Index before change: " + str(otherBot.pathHistoryIndex))
                            # logger.info("OtherBots coords based on history and index before index change: (y= " + str(otherBot.pathHistory[otherBot.pathHistoryIndex][0]) + ", x= " + str(otherBot.pathHistory[otherBot.pathHistoryIndex][1]) + ")")
                            logger.info("OtherBots otherBot.y and other bot.x before index change: (" + str(otherBot.y) + ", " + str(otherBot.x) + ")")
                            logger.info("Amount being subtracted (longer path length - shorter path length): " + str(lengthOfOtherBotPath - lengthOfBotPath))

                            logger.info("otherBot.pathHistoryIndex before adjustment:" + str(otherBot.pathHistoryIndex))
                            # findIndex = otherBot.pathHistory.index((otherBot.pathHistory[otherBot.pathHistoryIndex][0], otherBot.pathHistory[otherBot.pathHistoryIndex][1]))
                            # logger.info("results of findIndex before adjustment:" + str(findIndex))

                            otherBot.pathHistoryIndex = otherBot.pathHistoryIndex - lengthOfOtherBotPath + lengthOfBotPath

                            logger.info("otherBot.pathHistoryIndex after adjustment:" + str(otherBot.pathHistoryIndex))
                            findIndex = otherBot.pathHistory.index((otherBot.pathHistory[otherBot.pathHistoryIndex][0], otherBot.pathHistory[otherBot.pathHistoryIndex][1]))
                            logger.info("results of findIndex after adjustment:" + str(findIndex))

                            logger.info("Index after change: " + str(otherBot.pathHistoryIndex))
                            logger.info("OtherBots coords based on history and index after index change: (y= " + str(
                                otherBot.pathHistory[otherBot.pathHistoryIndex][0]) + ", x= " + str(
                                otherBot.pathHistory[otherBot.pathHistoryIndex][1]) + ")")
                            logger.info("OtherBots otherBot.y and otherBot.x AFTER index change: (" + str(otherBot.y) + ", " + str(otherBot.x) + ")")
                            logger.info("END DONE END")

                        circles.append((otherBot.pathHistory[otherBot.pathHistoryIndex][0],
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
                        logger.info("In logic for otherBotHasShortSection AND BotIsInSection is False")
                        logger.info("Safely removing points in bot's pathHistory. Starting at index (incl) " + str(botStartIndex + 1) + ". Stopping at index (excl) " + str(botEndIndex))

                        if highlightMode:
                            # Colour path being removed all white to see steps
                            for i in range(botStartIndex + 1, botEndIndex):
                                numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = [255, 255, 255, 255]
                            self.pause()
                            # for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                            #     numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = pointGrid[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]][0]

                        for i in range(botStartIndex + 1, botEndIndex):
                            self.removeBotMetaDataFromPoint(bot, bot.pathHistory[i])

                        logger.info("Changing bots pathHistory:" +
                                    "\n 1st chunk is bot.pathHistory from start up to index (excl) " + str(botStartIndex) +
                                    "\n 2nd chunk is otherBot.pathHistory from index " + str(otherBotStartIndex) + " (incl) up to index " + str(otherBotEndIndex) + " (excl)" +
                                    "\n 3rd chunk is bot.pathHistory from index " + str(botEndIndex) + " (incl) to end of otherBot.pathHistory")

                        logger.info("bots coords based on history and index before HISTORY CHANGE change: (y= " + str(bot.pathHistory[bot.pathHistoryIndex][0]) + ", x= " + str(bot.pathHistory[bot.pathHistoryIndex][1]) + ")")
                        logger.info("bot.y and bot.x before HISTORY change: (" + str(bot.y) + ", " + str(bot.x) + ")")

                        bot.pathHistory = bot.pathHistory[:botStartIndex] + otherBot.pathHistory[otherBotStartIndex:otherBotEndIndex] + bot.pathHistory[botEndIndex:]

                        if bot.pathHistoryIndex >= botEndIndex:
                            logger.info("bot is currently past section being edited, so it's index must be changed.")
                            logger.info("Index before change: " + str(bot.pathHistoryIndex))
                            # logger.info("OtherBots coords based on history and index before index change: (y= " + str(otherBot.pathHistory[otherBot.pathHistoryIndex][0]) + ", x= " + str(otherBot.pathHistory[otherBot.pathHistoryIndex][1]) + ")")
                            logger.info("bot.y and bot.x before index change: (" + str(bot.y) + ", " + str(bot.x) + ")")
                            logger.info("Amount being subtracted (longer path length - shorter path length): " + str(lengthOfBotPath - lengthOfOtherBotPath))

                            logger.info("bot.pathHistoryIndex before adjustment:" + str(bot.pathHistoryIndex))
                            # findIndex = otherBot.pathHistory.index((otherBot.pathHistory[otherBot.pathHistoryIndex][0], otherBot.pathHistory[otherBot.pathHistoryIndex][1]))
                            # logger.info("results of findIndex before adjustment:" + str(findIndex))

                            bot.pathHistoryIndex = bot.pathHistoryIndex - lengthOfBotPath + lengthOfOtherBotPath

                            logger.info("bot.pathHistoryIndex after adjustment:" + str(bot.pathHistoryIndex))
                            findIndex = bot.pathHistory.index((bot.pathHistory[bot.pathHistoryIndex][0],
                                                                    bot.pathHistory[bot.pathHistoryIndex][1]))
                            logger.info("results of findIndex after adjustment:" + str(findIndex))

                            logger.info("Index after change: " + str(bot.pathHistoryIndex))
                            logger.info("bots coords based on history and index after index change: (y= " + str(
                                bot.pathHistory[bot.pathHistoryIndex][0]) + ", x= " + str(
                                bot.pathHistory[bot.pathHistoryIndex][1]) + ")")
                            logger.info(
                                "bot.y and bot.x AFTER index change: (" + str(bot.y) + ", " + str(bot.x) + ")")
                            logger.info("END DONE END\n\n")

                        circles.append((bot.pathHistory[bot.pathHistoryIndex][0],
                                        bot.pathHistory[bot.pathHistoryIndex][1]))

                        for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                            self.addBotMetaDataToPoint(bot, otherBot.pathHistory[i])

                        if highlightMode:
                            self.pause()

            # End of iteration, clear section specific things. like circles
            dataTransferred = True
            totalDataTransferred += min(lengthOfBotPath, lengthOfOtherBotPath)
            circles.clear()

        if dataTransferred:
            bot.timeoutCounter = int(totalDataTransferred / 100)
            otherBot.timeoutCounter = int(totalDataTransferred / 100)

    # TODO look into making these functions accept ranges instead of individual points
    def removeBotMetaDataFromPoint(self, bot, point):
        pointData = pointGrid[point[0]][point[1]]
        try:
            pointData.remove(bot.pathRGB)
            bot.intersections.remove(point)
        except ValueError:
            pass
        numpyEnvironment[point[0]][point[1]] = pointData[0] if len(pointData) != 0 else [0, 0, 0, 255]

    def addBotMetaDataToPoint(self, bot, point):
        pointData = pointGrid[point[0]][point[1]]
        if bot.pathRGB not in pointData:
            pointData.append(bot.pathRGB)
        if len(pointData) != 1:
            bot.intersections.append(point)
        numpyEnvironment[point[0]][point[1]] = pointData[0]

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
                pathToPointInPixels = self.getMovePixels(bot.y, bot.x, yPoint, xPoint)
                if len(pathToPointInPixels) == 0:
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
                newPathPixels = self.getMovePixels(bot.y, bot.x, bestPoint[1], bestPoint[2])
            else:
                pointsFoundInHistory.sort(key=lambda x: x[0])
                bestPoint = pointsFoundInHistory[0]
                newPathPixels = self.getMovePixels(bestPoint[1], bestPoint[2], bot.y, bot.x)

            start, stop, step = (bot.pathHistoryIndex, bestPoint[0] + 1, 1) if forward else (bot.pathHistoryIndex, bestPoint[0] - 1, -1)
            for i in range(start, stop, step):
                self.removeBotMetaDataFromPoint(bot, bot.pathHistory[i])

            # Check for intersections along updated path section and handle appropriately
            for i in range(len(newPathPixels)):
                self.addBotMetaDataToPoint(bot, newPathPixels[i])

            sectionStart, sectionStop = (bot.pathHistoryIndex, bestPoint[0] + 1) if forward else (bestPoint[0], bot.pathHistoryIndex + 1)
            bot.pathHistory = bot.pathHistory[:sectionStart] + newPathPixels + bot.pathHistory[sectionStop:]

            if not forward:
                bot.pathHistoryIndex = bestPoint[0] + len(newPathPixels) - 1

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

    def canCommunicateWithBot(self, bot, rads, distance, otherBot):
        pass


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


# Main function
if __name__ == "__main__":
    # y1, x1, y2, x2 = 15, 15, 95, 30
    # rads = getRadiansOfPoints(y1, x1, y2, x2)
    # print(math.degrees(rads))
    # dist = math.sqrt((y1-y2)**2 + (x1-x2)**2)
    # print(getCoordsFromPointAndAngle(y1, x1, rads, dist))
    #
    # rads = getRadiansOfPoints(0, 0, -1, -1)
    # print(math.degrees(rads))
    #
    #
    #
    # input()

    # Initialize PIL images, data, and tools
    originalBG = Image.open("environment1.png")
    numpyEnvironment = np.array(originalBG)
    height, width = numpyEnvironment.shape[0], numpyEnvironment.shape[1]
    originalBG.close()

    pointGrid = []
    for row in range(height):
        tempRow = []
        for col in range(width):
            tempRow.append([])
        pointGrid.append(tempRow)

    if GUI:
        # Initialize tkinter tools and open window
        root = tk.Tk()
        root.title("Swarm Pathfinding")
        root.geometry("+0+5")
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

    # Make a matrix for calculating where bots can and can't go (0 is free space, 1 is impassable terrain)
    impassableTerrainArray = []
    for row in range(height):
        tempRow = []
        for col in range(width):
            pixel = numpyEnvironment[row][col]
            value = pixel[0] + pixel[1] + pixel[2]
            if value == 0:
                tempRow.append(0)
            else:
                tempRow.append(1)
        impassableTerrainArray.append(tempRow)

    # Set up thread logging
    logging.basicConfig(filename="threadLogger.log",
                        format='%(asctime)s %(message)s',
                        filemode='w',
                        level=logging.DEBUG)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logging.info("Logger ready")

    # Spawn bots and launch thread
    for index in range(numberOfBots):
        bot = Bot(index)
        listOfBots.append(bot)
    myThread = MyThread(listOfBots, numEquipment)
    myThread.isDaemon()
    myThread.start()

    if GUI:
        for bot in listOfBots:
            bot.drawCircle = window.create_oval(bot.x - botDrawRadius, bot.y - botDrawRadius, bot.x + botDrawRadius,
                                                bot.y + botDrawRadius, fill=bot.pathHex, outline=bot.pathHex)

        startEndLines = drawStartEndLines(window)

        while True:
            # startTime = time.time()
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
            for c in circles:
                window.create_rectangle(c[1] - botDrawRadius, c[0] - botDrawRadius, c[1] + botDrawRadius,
                                               c[0] + botDrawRadius, fill='white', outline='white')

            window.pack()
            window.update()
            # print("Time taken for entire update", time.time() - startTime)
            if readyToExit:
                time.sleep(1)
                root.destroy()
                exit()

