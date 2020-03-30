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
from numba import jit


# Global variables and settings
startCoord = [500, 125]  # (Y, X)
endCoord = [225, 650]  # (Y, X)
listOfBots = []
numberOfBots = 4
botVisionRadius = 100
botStepSize = 10
botSlowdown = 0.05
numberOfDraws = 0
botDrawRadius = 5
paused = False
myThread = None
numRounds = 0
maxBotTurnInRads = 0.25
workingBG = None
intersectionsDict = dict()
circles = []

class Bot:
    def __init__(self, botNumber):
        self.pathRGB = np.array([randint(50, 255), randint(50, 255), randint(50, 255), 255])
        self.pathHex = "#" + str(hex(self.pathRGB[0]))[2:] + str(hex(self.pathRGB[1]))[2:] + str(hex(self.pathRGB[2]))[2:]
        self.y = startCoord[0]
        self.x = startCoord[1]
        self.pathHistory = [(self.y, self.x)]
        self.number = botNumber
        self.drawCircle = 0
        self.drawCargo = 0
        self.hasSuccessfulPath = False
        self.isCarryingCargo = False
        self.pathHistoryIndex = 0
        self.direction = 2 * math.pi * random()
        self.intersections = [(startCoord[0], startCoord[1])]
        self.recentlySeenBots = list()

class MyThread(threading.Thread):
    def __init__(self, listOfBots):
        threading.Thread.__init__(self)
        self.paused = False
        self.pause_cond = threading.Condition(threading.Lock())
        self.bots = listOfBots

    def run(self):
        global numRounds
        global botVisionRadius
        while True:
            with self.pause_cond:
                while self.paused:
                    self.pause_cond.wait()
                shuffle(self.bots)
                for bot in self.bots:
                    # *****  LOGIC FOR EACH BOT STEP STARTS HERE *****

                    if not bot.hasSuccessfulPath:  # Bot is looking for destination
                        # Log current position
                        prevStep = (bot.y, bot.x)

                        # Check if bot can see/move to destination
                        distanceToDestination = math.sqrt((endCoord[0] - bot.y) ** 2 + (endCoord[1] - bot.x) ** 2)
                        if distanceToDestination <= botStepSize:
                            yStep = endCoord[0] - bot.y
                            xStep = endCoord[1] - bot.x
                            bot.hasSuccessfulPath = True
                            bot.pathHistoryIndex = len(bot.pathHistory) - 1
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
                        pathRGBAsList = bot.pathRGB[:3].tolist()
                        for i in range(len(pixelPath)):
                            pointColour = numpyEnvironment[pixelPath[i][0]][pixelPath[i][1]][:3].tolist()
                            if pointColour != [0, 0, 0] and pointColour != pathRGBAsList:
                                bot.intersections.append((pixelPath[i][0], pixelPath[i][1]))
                                pointHistory = intersectionsDict.get((pixelPath[i][0], pixelPath[i][1]))
                                if pointHistory is None:
                                    intersectionsDict[(pixelPath[i][0], pixelPath[i][1])] = [pointColour, pathRGBAsList]
                                else:
                                    if pathRGBAsList not in intersectionsDict[(pixelPath[i][0], pixelPath[i][1])]:
                                        intersectionsDict[(pixelPath[i][0], pixelPath[i][1])].append(pathRGBAsList)
                            bot.pathHistory.append(pixelPath[i])
                            numpyEnvironment[pixelPath[i][0]][pixelPath[i][1]] = [bot.pathRGB[0], bot.pathRGB[1], bot.pathRGB[2], 255]

                        # Move bot
                        bot.y += yStep
                        bot.x += xStep



                    else:   # Bot has found destination and is transporting cargo
                        # Bot is carrying cargo and is moving towards destination
                        if bot.isCarryingCargo:
                            # logger.info("\n\nBot carrying cargo, moving towards destination")
                            # Apply smoothing to bot's path as it moves forward
                            perimeterCoords = self.getPerimeterCoords(bot.x, bot.y)
                            pointsFoundInHistory = []
                            for point in perimeterCoords:
                                xPoint = 0 if point[0] < 0 else width - 1 if point[0] > width - 1 else point[0]
                                yPoint = 0 if point[1] < 0 else height - 1 if point[1] > height - 1 else point[1]

                                # Disregard point if it's not a valid destination
                                if impassableTerrainArray[yPoint][xPoint] == 1:
                                    continue

                                # Check if perimeter point is same colour as bot's colour
                                if np.array_equal(numpyEnvironment[yPoint][xPoint], bot.pathRGB):

                                    # Make sure the path to the point being examined is valid and not blocked
                                    pathToPointInPixels = self.getMovePixels(bot.y, bot.x, yPoint, xPoint)
                                    if len(pathToPointInPixels) == 0:
                                        continue

                                    # Make sure point isn't in the wrong direction (avoids looking through entire path history for no reason)
                                    backTrackIndex = int(bot.pathHistoryIndex - (1.5 * botStepSize)) if bot.pathHistoryIndex > (1.5 * botStepSize) else 0
                                    if point in bot.pathHistory[backTrackIndex:bot.pathHistoryIndex]:
                                        continue

                                    # Look through path history in the appropriate direction and add perimeter points and their indices (in bot's path history) to a temporary list
                                    for i in range(bot.pathHistoryIndex, len(bot.pathHistory)):
                                        if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                                            pointsFoundInHistory.append((i, yPoint, xPoint))

                            # If we have found a viable shortcut, then adjust bot's path history and GUI
                            if len(pointsFoundInHistory) != 0:
                                # logger.info("Viable shortcut found")
                                # Determine which point provides the best shortcut (the farthest index)
                                pointsFoundInHistory.sort(key=lambda x: x[0], reverse=True)
                                bestPoint = pointsFoundInHistory[0]
                                pathRGBAsList = bot.pathRGB[:3].tolist()
                                # logger.info("Bot's current pathHistoryIndex: " + str(bot.pathHistoryIndex))
                                # logger.info("Bot's current coord: (y=" + str(bot.y) + ", x=" + str(bot.x) + ")")
                                # logger.info("bestPoint found in bots history: " + str(bestPoint))

                                # Draw black lines over chunk of path that is not part of shortest path
                                # Remove intersections from appropriate coords in outdated path history (no longer intersections there)
                                # Draw the colour of path that was there before, if applicable
                                start = bot.pathHistoryIndex
                                # logger.info("Purging indices. [" + str(start) + ", " + str(bestPoint[0]+1))
                                for i in range(bot.pathHistoryIndex, bestPoint[0]+1):
                                    self.safelyRemoveIndexFromBotPathHistory(bot, i)



                                # Check for intersections along updated path section and handle appropriately
                                newPathPixels = self.getMovePixels(bot.y, bot.x, bestPoint[1], bestPoint[2])
                                # logger.info("NewPathPixels = " + str(newPathPixels))
                                for i in range(len(newPathPixels)):
                                    pointColour = numpyEnvironment[newPathPixels[i][0]][newPathPixels[i][1]][:3].tolist()
                                    if pointColour != [0, 0, 0] and pointColour != pathRGBAsList:
                                        bot.intersections.append((newPathPixels[i][0], newPathPixels[i][1]))
                                        pointHistory = intersectionsDict.get((newPathPixels[i][0], newPathPixels[i][1]))
                                        if pointHistory is None or len(pointHistory) == 0:
                                            intersectionsDict[(newPathPixels[i][0], newPathPixels[i][1])] = [pointColour, pathRGBAsList]
                                        else:
                                            intersectionsDict[(newPathPixels[i][0], newPathPixels[i][1])].append(pathRGBAsList)
                                # logger.info("1st:" + str(bot.pathHistory[:bot.pathHistoryIndex]))
                                # logger.info("Mid:" + str(newPathPixels))
                                # logger.info("End:" + str(bot.pathHistory[bestPoint[0]+1:]))

                                # Add the new path to path history and add the lines to be drawn to the queue
                                # logger.info("Len 1st " + str(len(bot.pathHistory[:bot.pathHistoryIndex])))
                                # logger.info("Len 2nd " + str(len(newPathPixels)))
                                # logger.info("Len 2rd " + str(len(bot.pathHistory[bestPoint[0]+1:])))
                                # logger.info("Len history before change "+ str(len(bot.pathHistory)))
                                bot.pathHistory = bot.pathHistory[:bot.pathHistoryIndex] + newPathPixels + bot.pathHistory[bestPoint[0]+1:]
                                # logger.info("Len history after change "+ str(len(bot.pathHistory)))
                                for point in newPathPixels:
                                    numpyEnvironment[point[0]][point[1]] = [bot.pathRGB[0], bot.pathRGB[1], bot.pathRGB[2], 255]


                                # Go forward through path history
                                bot.pathHistoryIndex += botStepSize
                                if bot.pathHistoryIndex >= len(bot.pathHistory):
                                    bot.pathHistoryIndex = len(bot.pathHistory) - 1
                                    bot.isCarryingCargo = False
                                bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                bot.x = bot.pathHistory[bot.pathHistoryIndex][1]


                            else:
                                pathRGBAsList = bot.pathRGB[:3].tolist()
                                stopIndex = bot.pathHistoryIndex + botStepSize if bot.pathHistoryIndex + botStepSize <= len(bot.pathHistory) else len(bot.pathHistory)
                                for i in range(bot.pathHistoryIndex+1, stopIndex):
                                    pointColour = numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]][:3].tolist()
                                    if (pointColour != [0, 0, 0] and pointColour != pathRGBAsList) or bot.pathHistory[i] == (endCoord[0], endCoord[1]):
                                        bot.intersections.append(bot.pathHistory[i])
                                        pointHistory = intersectionsDict.get(bot.pathHistory[i])
                                        if pointHistory is None or len(pointHistory) == 0:
                                            intersectionsDict[bot.pathHistory[i]] = [pointColour, pathRGBAsList]
                                        else:
                                            intersectionsDict[bot.pathHistory[i]].append(pathRGBAsList)


                                # Go forward through path history
                                bot.pathHistoryIndex += botStepSize
                                if bot.pathHistoryIndex >= len(bot.pathHistory):
                                    bot.pathHistoryIndex = len(bot.pathHistory) - 1
                                    bot.isCarryingCargo = False
                                bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                bot.x = bot.pathHistory[bot.pathHistoryIndex][1]




                        # Bot is not carrying cargo and is heading back to start
                        else:
                            # logger.info("\n\nBot not carrying cargo, moving backwards towards start")
                            # Apply smoothing to bot's path as it moves backwards
                            perimeterCoords = self.getPerimeterCoords(bot.x, bot.y)
                            pointsFoundInHistory = []
                            for point in perimeterCoords:
                                xPoint = 0 if point[0] < 0 else width - 1 if point[0] > width - 1 else point[0]
                                yPoint = 0 if point[1] < 0 else height - 1 if point[1] > height - 1 else point[1]

                                # Disregard point if it's not a valid destination
                                if impassableTerrainArray[yPoint][xPoint] == 1:
                                    continue

                                # Check if perimeter point is same colour as bot's colour
                                if np.array_equal(numpyEnvironment[yPoint][xPoint], bot.pathRGB):

                                    # Make sure the path to the point being examined is valid and not blocked
                                    pathToPointInPixels = self.getMovePixels(bot.y, bot.x, yPoint, xPoint)
                                    if len(pathToPointInPixels) == 0:
                                        continue

                                    # Make sure point isn't in the wrong direction (avoids looking through entire path history for no reason)

                                    backTrackIndex = int(bot.pathHistoryIndex + (1.5 * botStepSize)) if bot.pathHistoryIndex + (1.5 * botStepSize) < len(bot.pathHistory) else len(bot.pathHistory)-1
                                    if point in bot.pathHistory[bot.pathHistoryIndex:backTrackIndex+1]:
                                        continue

                                    # Look through path history in the appropriate direction and add perimeter points and their indices (in bot's path history) to a temporary list
                                    for i in range(bot.pathHistoryIndex, -1, -1):
                                        if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                                            pointsFoundInHistory.append((i, yPoint, xPoint))

                            # If we have found a viable shortcut, then adjust bot's path history and GUI
                            if len(pointsFoundInHistory) != 0:
                                # Determine which point provides the best shortcut (the farthest index)
                                pointsFoundInHistory.sort(key=lambda x: x[0])
                                bestPoint = pointsFoundInHistory[0]
                                pathRGBAsList = bot.pathRGB[:3].tolist()
                                # logger.info("Bot's current pathHistoryIndex: " + str(bot.pathHistoryIndex))
                                # logger.info("Bot's current coord: (y=" + str(bot.y) + ", x=" + str(bot.x) + ")")
                                # logger.info("bestPoint found in bots history: " + str(bestPoint))

                                # Draw black pixels over chunk of path that is not part of shortest path
                                # logger.info("Purging indices. [" + str(bot.pathHistoryIndex) + ", " + str(bestPoint[0]-1) + ", step = -1)")
                                for i in range(bot.pathHistoryIndex, bestPoint[0]-1, -1):
                                    self.safelyRemoveIndexFromBotPathHistory(bot, i)


                                # Add the new path to path history and add the points to be drawn to the queue
                                newPathPixels = self.getMovePixels(bestPoint[1], bestPoint[2], bot.y, bot.x)
                                # logger.info("NewPathPixels = " + str(newPathPixels))
                                for i in range(len(newPathPixels)):
                                    pointColour = numpyEnvironment[newPathPixels[i][0]][newPathPixels[i][1]][:3].tolist()
                                    if pointColour != [0, 0, 0] and pointColour != pathRGBAsList:
                                        bot.intersections.append((newPathPixels[i][0], newPathPixels[i][1]))
                                        pointHistory = intersectionsDict.get((newPathPixels[i][0], newPathPixels[i][1]))
                                        if pointHistory is None or len(pointHistory) == 0:
                                            intersectionsDict[(newPathPixels[i][0], newPathPixels[i][1])] = [pointColour, pathRGBAsList]
                                        else:
                                            intersectionsDict[(newPathPixels[i][0], newPathPixels[i][1])].append(pathRGBAsList)

                                # logger.info("1st:" + str(bot.pathHistory[:bestPoint[0]]))
                                # logger.info("Mid:" + str(newPathPixels))
                                # logger.info("End:" + str(bot.pathHistory[bot.pathHistoryIndex+1:]))

                                # Add the new path to path history and add the lines to be drawn to the queue
                                # logger.info("Len 1st " + str(len(bot.pathHistory[:bestPoint[0]])))
                                # logger.info("Len 2nd " + str(len(newPathPixels)))
                                # logger.info("Len 2rd " + str(len(bot.pathHistory[bot.pathHistoryIndex+1:])))
                                # logger.info("Len history before change "+ str(len(bot.pathHistory)))

                                bot.pathHistory = bot.pathHistory[:bestPoint[0]] + newPathPixels + bot.pathHistory[bot.pathHistoryIndex+1:]
                                bot.pathHistoryIndex = bot.pathHistoryIndex - (bot.pathHistoryIndex - bestPoint[0]) + len(newPathPixels) -1
                                # logger.info("Len history after change " + str(len(bot.pathHistory)))
                                for point in newPathPixels:
                                    numpyEnvironment[point[0]][point[1]] = [bot.pathRGB[0], bot.pathRGB[1], bot.pathRGB[2], 255]

                                # Go backwards through path history
                                bot.pathHistoryIndex -= botStepSize
                                if bot.pathHistoryIndex < 0:
                                    bot.pathHistoryIndex = 0
                                    bot.isCarryingCargo = True
                                bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                bot.x = bot.pathHistory[bot.pathHistoryIndex][1]

                            else:
                                # no shortcut, move ten, check for intersections
                                pathRGBAsList = bot.pathRGB[:3].tolist()
                                stopIndex = bot.pathHistoryIndex-botStepSize if bot.pathHistoryIndex-botStepSize > -1 else -1
                                for i in range(bot.pathHistoryIndex-1, stopIndex, -1):
                                    pointColour = numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]][:3].tolist()
                                    if (pointColour != [0, 0, 0] and pointColour != pathRGBAsList) or bot.pathHistory[i] == (startCoord[0], startCoord[1]):
                                        bot.intersections.append((bot.pathHistory[i][0], bot.pathHistory[i][1]))
                                        pointHistory = intersectionsDict.get((bot.pathHistory[i][0], bot.pathHistory[i][1]))
                                        if pointHistory is None or len(pointHistory) == 0:
                                            intersectionsDict[bot.pathHistory[i]] = [pointColour, pathRGBAsList]
                                        else:
                                            intersectionsDict[bot.pathHistory[i]].append(pathRGBAsList)

                                # Go backwards through path history
                                bot.pathHistoryIndex -= botStepSize
                                if bot.pathHistoryIndex < 0:
                                    bot.pathHistoryIndex = 0
                                    bot.isCarryingCargo = True
                                bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                                bot.x = bot.pathHistory[bot.pathHistoryIndex][1]
                        # TODO ------    Check for other bots to communicate with --------
                        for otherBot in listOfBots:
                            if not (bot.pathRGB == otherBot.pathRGB).all():  # If other bot is not same bot
                                if (bot.x - otherBot.x) ** 2 + (
                                        bot.y - otherBot.y) ** 2 < botVisionRadius ** 2:  # If other bot within vision range
                                    if otherBot.pathRGB.tolist() not in bot.recentlySeenBots:
                                        bot.recentlySeenBots.append(otherBot.pathRGB.tolist())
                                        otherBot.recentlySeenBots.append(bot.pathRGB.tolist())
                                        self.compareAndUpdatePaths(bot, otherBot)

                                else:  # Other bot is out of range, so make sure it's removed from recently seen list
                                    # TODO maybe add a counter so that bots don't go in, go out, go in, go out, etc every turn
                                    # something like a "if we've seen each other in the last 10 moves or so"
                                    try:
                                        bot.recentlySeenBots.remove(otherBot.pathRGB.tolist())
                                    except ValueError:
                                        pass

                                    try:
                                        otherBot.recentlySeenBots.remove(bot.pathRGB.tolist)
                                    except ValueError:
                                        pass
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
            botPathAsPixels = self.getMovePixels(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
            if len(botPathAsPixels) != 0:
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

    @jit(nopython=True)
    def applyPathSmoothing(self, bot, direction):
        perimeterCoords = self.getPerimeterCoords(bot.x, bot.y)
        pointsFoundInHistory = []
        for point in perimeterCoords:
            xPoint = 0 if point[0] < 0 else width - 1 if point[0] > width - 1 else point[0]
            yPoint = 0 if point[1] < 0 else height - 1 if point[1] > height - 1 else point[1]

            # Disregard point if it's not a valid destination
            if impassableTerrainArray[yPoint][xPoint] == 1:
                continue

            # Check if perimeter point is same colour as bot's colour
            if np.array_equal(numpyEnvironment[yPoint][xPoint], bot.pathRGB):

                # Make sure the path to the point being examined is valid and not blocked
                pathToPointInPixels = self.getMovePixels(bot.y, bot.x, yPoint, xPoint)
                if len(pathToPointInPixels) == 0:
                    continue

                # Make sure point isn't in the wrong direction (avoids looking through entire path history for no reason)
                if direction == 'forward':
                    backTrackIndex = int(bot.pathHistoryIndex - (1.5*botStepSize)) if bot.pathHistoryIndex > (1.5*botStepSize) else 0
                    if point in bot.pathHistory[backTrackIndex:bot.pathHistoryIndex]:
                        continue
                else:
                    backTrackIndex = int(bot.pathHistoryIndex + (1.5*botStepSize)) if bot.pathHistoryIndex < len(bot.pathHistory) - (1.5*botStepSize) else len(bot.pathHistory)
                    if point in bot.pathHistory[bot.pathHistoryIndex:backTrackIndex]:
                        continue

                # Look through path history in the appropriate direction and add perimeter points and their indices (in bot's path history) to a temporary list
                start = bot.pathHistoryIndex
                stop = len(bot.pathHistory) if direction == 'forward' else 0
                step = 1 if direction == 'forward' else -1
                for i in range(start, stop, step):
                    if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                        pointsFoundInHistory.append((i, yPoint, xPoint))

        # If we have found a viable shortcut, then adjust bot's path history and GUI
        if len(pointsFoundInHistory) != 0:
            # Determine which point provides the best shortcut (the farthest index)
            if direction == 'forward':
                pointsFoundInHistory.sort(key=lambda x: x[0], reverse=True)
            else:
                pointsFoundInHistory.sort(key=lambda x: x[0])
            bestPoint = pointsFoundInHistory[0]

            # TODO adjust these off by ones to see if it improves "breaks" in path
            # Draw black lines over chunk of path that is not part of shortest path
            start = bot.pathHistoryIndex
            stop = bestPoint[0] - 1 if direction == 'forward' else bestPoint[0] + 1 #These 'ones' ensure we don't go past either end of pathHistory
            step = 1 if direction == 'forward' else -1
            for i in range(bot.pathHistoryIndex, stop, step):
                if direction == 'forward':
                    bot.pathToBeCleared.put((bot.pathHistory[i], bot.pathHistory[i + 1]))
                else:
                    bot.pathToBeCleared.put((bot.pathHistory[i], bot.pathHistory[i - 1]))

            # Add the new path to path history and add them lines to be drawn to the queue
            newPathPixels = self.getMovePixels(bot.y, bot.x, bestPoint[1], bestPoint[2])
            if direction == 'forward':
                bot.pathHistory = bot.pathHistory[:bot.pathHistoryIndex] + newPathPixels + bot.pathHistory[bestPoint[0]:]
            else:
                bot.pathHistory = bot.pathHistory[:bestPoint[0]+1] + newPathPixels + bot.pathHistory[bot.pathHistoryIndex:]
                bot.pathHistoryIndex = bot.pathHistoryIndex - (bot.pathHistoryIndex - bestPoint[0]) + len(newPathPixels)

            bot.pathToBeDrawn.put((bot.pathHistory[bot.pathHistoryIndex], (bestPoint[1], bestPoint[2])))

        else:
            logger.info("No viable")

    # Function implemented with the help of http://www.roguebasin.com/index.php?title=Bresenham%27s_Line_Algorithm
    # Checks each point in a line to ensure a bot doesn't "jump" over an illegal area
    @staticmethod
    def getMovePixels(currentY, currentX, futureY, futureX):
        if (0 <= futureY < height) and (0 <= futureX < width):

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
            for x in range(currentX, futureX + 1):
                coords = (x, y)
                if lineIsSteep:
                    coords = (y, x)
                coordList.append((coords[1], coords[0]))
                if impassableTerrainArray[coords[1]][coords[0]] == 1:
                    return []
                e -= abs(dy)
                if e < 0:
                    y += yStep
                    e += dx
            if startEndSwapped:
                coordList.reverse()
            return coordList

        else:
            return []

    def compareAndUpdatePaths(self, bot, otherBot):
        # EXCHANGE PATH INFO HERE
        # TODO also try out the naive solution (look through every point in paths and
        # if you hit an intersection, update both paths appropriately)
        if not bot.hasSuccessfulPath or not otherBot.hasSuccessfulPath:
            # TODO exchange info between bots if one bot does not know of a successful path
            return

        # Both bots have a successful path, so find intersections and optimize both paths

        # Find the intersections
        sharedIntersections = set()
        for point in bot.intersections:
            try:
                if otherBot.pathRGB[:3].tolist() in intersectionsDict[point]:
                    sharedIntersections.add(point)
                    # circles.append(point)
            except KeyError:
                pass
        for point in otherBot.intersections:
            try:
                if bot.pathRGB[:3].tolist() in intersectionsDict[point]:
                    sharedIntersections.add(point)
                    # circles.append(point)
            except KeyError:
                pass

        intersectionsInBotHistory = [x for x in bot.pathHistory if x in sharedIntersections]
        intersectionsInOtherBotsHistory = [x for x in otherBot.pathHistory if x in sharedIntersections]
        sharedPoints = [x for x in intersectionsInBotHistory if x in intersectionsInOtherBotsHistory]
        uniquePoints = [t for t in (set(tuple(i) for i in sharedPoints))]
        # sharedPoints = sorted(uniquePoints, key=lambda tup: tup[0], reverse=True)

        # Get the indexes of the intersections and the intersections (i, (y,x))
        # (with duplicates removed)
        botIndices = [(bot.pathHistory.index(x), x) for x in uniquePoints]
        botIndices = sorted(botIndices, key=lambda tup: tup[0])
        otherBotIndices = [(otherBot.pathHistory.index(x), x) for x in uniquePoints]
        otherBotIndices = sorted(otherBotIndices, key=lambda tup: tup[0])

        if len(botIndices) != len(otherBotIndices):
            logger.info("BIG PROBLEM")
            time.sleep(5)
        logger.info(str(sharedIntersections))
        logger.info("\n" + str(uniquePoints) + "\n" + str(botIndices) + "\n" + str(otherBotIndices) + "\n")

        for i in range(len(botIndices) - 2, -1, -1):
            # TODO if path length is the same, do nothing.
            # circles.append(botIndices[i][1])
            # circles.append(otherBotIndices[i][1])

            # logger.info("PAIRS: \nBot 1 is from " + str(bot1Indices[i]) + " to " + str(bot1Indices[i+1]) + ". \nBot 2 is from " + str(bot2Indices[i]) + " to " + str(bot2Indices[i+1]) + ".")
            botStartIndex = botIndices[i][0]
            botEndIndex = botIndices[i + 1][0]
            otherBotStartIndex = otherBotIndices[i][0]
            otherBotEndIndex = otherBotIndices[i + 1][0]
            lengthOfBotPath = botEndIndex - botStartIndex
            lengthOfOtherBotPath = otherBotEndIndex - otherBotStartIndex

            logger.info("\n\nCurrently examining these bot points:      " + str(botIndices[i]) + " " + str(botIndices[i+1]))
            logger.info("Currently examining these otherbot points: " + str(otherBotIndices[i]) + " " + str(otherBotIndices[i+1]))

            logger.info("\nbotStartIndex            " + str(botStartIndex) +
                        "\nbotEndIndex              " + str(botEndIndex) +
                        "\notherBotStartIndex       " + str(otherBotStartIndex) +
                        "\notherBotEndIndex         " + str(otherBotEndIndex) +
                        "\nlengthOfBotPath          " + str(lengthOfBotPath) +
                        "\nlengthOfOtherBotPath     " + str(lengthOfOtherBotPath) +
                        "\nlen(bot.pathHistory)     " + str(len(bot.pathHistory)) +
                        "\nlen(otherBot.pathHistory)" + str(len(otherBot.pathHistory)))

            # Don't adjust this section of paths for either bot since they're basically the same length
            if abs(lengthOfBotPath - lengthOfOtherBotPath) < 2:
                logger.info("*** IGNORING THESE POINTS. SECTIONS TOO CLOSE IN LENGTH ***")
                continue

            botIsInSection = False
            if botStartIndex < bot.pathHistoryIndex < botEndIndex:
                logger.info("bot pathHistoryIndex in between " + str(botStartIndex) + " and " + str(botEndIndex) + "\nBot is in between above intersections")
                botIsInSection = True

            otherBotIsInSection = False
            if otherBotStartIndex < otherBot.pathHistoryIndex < otherBotEndIndex:
                logger.info("otherbot pathHistoryIndex in between " + str(otherBotStartIndex) + " and " + str(otherBotEndIndex) + "\nOtherBot is in between above intersections")
                otherBotIsInSection = True

            botHasShorterSection = False
            otherBotHasShorterSection = False
            if lengthOfBotPath < lengthOfOtherBotPath:
                logger.info("Just compared section lengths. Bot has shorter section")
                botHasShorterSection = True
            else:
                logger.info("Just compared section lengths. OtherBot has shorter section")
                otherBotHasShorterSection = True

            if botHasShorterSection:  # bot has shorter section, so improve otherbot's section
                logger.info("In logic for botHasShorterSection")
                # print("bot has shorter section")
                if otherBotIsInSection:  # otherbot is in the current section, so we handle it specially
                    logger.info("In logic for botHasShortSection AND otherBotIsInSection is True")
                    # print("other bot in current section")
                    # pathToEarlierIntersection = otherBot.pathHistory[otherBot.pathHistoryIndex : otherBotStartIndex : -1]
                    # pathToLaterIntersection = otherBot.pathHistory[otherBot.pathHistoryIndex:otherBotEndIndex]
                    # if otherBot.isCarryingCargo: #bots going "forward"
                    #     print("other bot is going forward")
                    #     if len(pathToEarlierIntersection) + lengthOfBotPath < len(pathToLaterIntersection): # it's better for otherbot to go back before going forwards
                    #         print("otherbot is backtracking before going forward")
                    #         # remove old path between current point and next intersection
                    #         for i in range(otherBot.pathHistoryIndex+1, otherBotEndIndex):
                    #             safelyRemovePointFromBotPath(otherBot, i)
                    #         # insert path to earlier intersection, and bots shorter path
                    #         otherBot.pathHistory = otherBot.pathHistory[:otherBot.pathHistoryIndex] + pathToEarlierIntersection + bot.pathHistory[botStartIndex:botEndIndex] + otherBot.pathHistory[otherBotEndIndex:]
                    #
                    #     else: # shorter for other bot to continue on to later intersection
                    #         print("otherbot is going to later intersection")
                    #         # remove old path points
                    #         for i in range(otherBotStartIndex+1, otherBot.pathHistoryIndex):
                    #             safelyRemovePointFromBotPath(otherBot, i)
                    #
                    #         # insert path from later intersection
                    #         otherBot.pathHistory = otherBot.pathHistory[:otherBotStartIndex] + bot.pathHistory[botStartIndex:botEndIndex] + pathToLaterIntersection[::-1] + otherBot.pathHistory[bot.pathHistoryIndex:]
                    #
                    #         # update index
                    #         otherBot.pathHistoryIndex = otherBotStartIndex + lengthOfBotPath + len(pathToLaterIntersection) - 2 #minus 2 because len is not index friendly
                    #
                    #
                    #     # draw the new part of the path - same in both cases. bot has shorter path
                    #     for i in range(len(otherBot.pathHistory)):
                    #         numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = otherBot.pathRGB
                    #     for i in range(len(bot.pathHistory)):
                    #         numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = bot.pathRGB
                    #     time.sleep(2)
                    # else: # other bot is going backwards
                    #     pass
                    pass

                else:  # other bot is not in section, but bot has shorter section
                    logger.info("In logic for botHasShortSection AND otherBotIsInSection is False")
                    logger.info("Safely removing points in otherBot's pathHistory. Starting at index (incl) " + str(otherBotStartIndex + 1) +
                                ". Stopping at index (excl) " + str(otherBotEndIndex))

                    # Colour path being removed all white to see steps
                    for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                        numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = [255, 255, 255, 255]
                    self.pause()


                    for i in range(otherBotStartIndex + 1, otherBotEndIndex):
                        self.safelyRemoveIndexFromBotPathHistory(otherBot, i)
                    logger.info("Changing otherBots pathHistory:" +
                                "\n 1st chunk is otherBot.pathHistory from start up to index (excl) " + str(otherBotStartIndex) +
                                "\n 2nd chunk is bot.pathHistory from index " + str(botStartIndex) + " (incl) up to index " + str(botEndIndex) + " (excl)" +
                                "\n 3rd chunk is otherBot.pathHistory from index " + str(otherBotEndIndex) + " (incl) to end of otherBot.pathHistory")
                    otherBot.pathHistory = otherBot.pathHistory[:otherBotStartIndex] + bot.pathHistory[botStartIndex:botEndIndex] + otherBot.pathHistory[otherBotEndIndex:]

                    if otherBot.pathHistoryIndex >= otherBotEndIndex:
                        logger.info("OtherBot is currently past section being edited, so it's index must be changed.")
                        logger.info("Index before change: " + str(otherBot.pathHistoryIndex))
                        logger.info("Amount being subtracted (longer path length - shorter path length): " + str(lengthOfOtherBotPath - lengthOfBotPath))
                        otherBot.pathHistoryIndex = otherBot.pathHistoryIndex - lengthOfOtherBotPath + lengthOfBotPath
                        logger.info("Index after change: " + str(otherBot.pathHistoryIndex))

                    logger.info("Redrawing paths for both bots, bot first, then otherBot")
                    # redraw bot paths to do sanity checks
                    for i in range(len(bot.pathHistory)):
                        numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = bot.pathRGB
                    for i in range(len(otherBot.pathHistory)):
                        numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = otherBot.pathRGB

                    self.pause()

            else:  # otherbot has shorter section, so improve bot's section
                if botIsInSection:
                    pass

                else:  # bot is not in section, but other bot has shorter section
                    # for i in range(botStartIndex + 1, botEndIndex):
                    #     self.safelyRemovePointFromBotPath(bot, i)
                    # bot.pathHistory = bot.pathHistory[:botStartIndex] + otherBot.pathHistory[otherBotStartIndex:otherBotEndIndex] + bot.pathHistory[botStartIndex:]
                    # if bot.pathHistoryIndex > botEndIndex:
                    #     bot.pathHistoryIndex -= (lengthOfBotPath - lengthOfOtherBotPath)
                    #
                    # # redraw bot paths to do sanity checks
                    # for i in range(len(otherBot.pathHistory)):
                    #     numpyEnvironment[otherBot.pathHistory[i][0]][otherBot.pathHistory[i][1]] = otherBot.pathRGB
                    # for i in range(len(bot.pathHistory)):
                    #     numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = bot.pathRGB
                    pass
        # logger.info("\n" + str(sharedPoints) + "\n" + str(bot1Indices) + "\n" + str(bot2Indices) + "\n")

        circles.clear()

    def safelyRemoveIndexFromBotPathHistory(self, bot, i):
        numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = [0, 0, 0, 255]
        # Remove point from intersection dictionary
        try:
            intersectionsDict[bot.pathHistory[i]].remove(bot.pathRGB[:3].tolist())
            prevCol = intersectionsDict[bot.pathHistory[i]][len(intersectionsDict[bot.pathHistory[i]]) - 1]
            numpyEnvironment[bot.pathHistory[i][0]][bot.pathHistory[i][1]] = [prevCol[0], prevCol[1], prevCol[2], 255]

            if len(intersectionsDict[bot.pathHistory[i]]) < 2:
                del intersectionsDict[bot.pathHistory[i]]
        except ValueError:
            pass
        except KeyError:
            pass
        # Remove point from bot's intersections list
        try:
            bot.intersections.remove(bot.pathHistory[i])
            # bot.intersections = [x for x in bot.intersections if x[:2] != bot.pathHistory[i]]
        except ValueError:
            pass

    def safelyInsertPointIntoBotPathHistory(self, point, bot, index):
        pass


def drawStartEndLines(w):
    half = 15
    start1 = w.create_line(startCoord[1] - half, startCoord[0] - half, startCoord[1] + half, startCoord[0] + half, fill='#00FF00', width=4)
    start2 = w.create_line(startCoord[1] + half, startCoord[0] - half, startCoord[1] - half, startCoord[0] + half, fill='#00FF00', width=4)
    end1 = w.create_line(endCoord[1] - half, endCoord[0] - half, endCoord[1] + half, endCoord[0] + half, fill='#e6194B', width=4)
    end2 = w.create_line(endCoord[1] + half, endCoord[0] - half, endCoord[1] - half, endCoord[0] + half, fill='#e6194B', width=4)
    return [start1, start2, end1, end2]

def pauseButton():
    # global paused
    # if not paused:
    #     paused = True
    #     myThread.pause()
    # else:
    #     paused = False
    #     myThread.resume()

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

    # Initialize PIL images, data, and tools
    originalBG = Image.open("environment1.png")
    numpyEnvironment = np.array(originalBG)
    height, width = numpyEnvironment.shape[0], numpyEnvironment.shape[1]
    originalBG.close()

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
    # window.bind("<Button-1>", clickCallback)
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
    myThread = MyThread(listOfBots)
    myThread.start()

    for bot in listOfBots:
        bot.drawCircle = window.create_oval(bot.x - botDrawRadius,  bot.y - botDrawRadius, bot.x + botDrawRadius, bot.y + botDrawRadius, fill=bot.pathHex, outline=bot.pathHex)

    startEndLines = drawStartEndLines(window)

    # Main loop. Save and reload image periodically to keep tkinter from slowing down
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
            bot.drawCircle = window.create_oval(bot.x - botDrawRadius, bot.y - botDrawRadius, bot.x + botDrawRadius,
                                           bot.y + botDrawRadius, fill=bot.pathHex, outline=bot.pathHex)
            if bot.isCarryingCargo:
                window.delete(bot.drawCargo)
                bot.drawCargo = window.create_rectangle(bot.x - botDrawRadius - 2, bot.y - (1.5 * botDrawRadius),
                                                   bot.x + botDrawRadius + 2, bot.y - (0.5 * botDrawRadius),
                                                   fill='gray78', outline='gray78')
        for c in circles:
            window.create_oval(c[1] - botDrawRadius, c[0] - botDrawRadius, c[1] + botDrawRadius,
                                           c[0] + botDrawRadius, fill='white', outline='white')

        window.pack()
        window.update()
        # print("Time taken for entire update", time.time() - startTime)
