#TODO
# -look into if object attribute (foo.bar) lookups are actually super slow ! (33% slower)
# -try out using numpy array for basically all GUI stuff and then update everything each frame. seems to fast enough
# -maybe try implementing more functions that can use NUMBA to get better speeds

# Import required libraries
import math
import queue
import threading
import logging
import time
from PIL import Image, ImageTk
import tkinter as tk
from random import randint, shuffle, random, uniform
import numpy as np
from numba import jit, jitclass

# Global variables and settings
botPathColours = [("Red", '#e6194B'), ("Green", '#3cb44b'), ("Yellow", '#ffe119'), ("Blue", '#4363d8'),
                     ("Orange", '#f58231'), ("Purple", '#911eb4'), ("Cyan", '#42d4f4'), ("Magenta", '#f032e6'),
                     ("Lime", '#bfef45'), ("Pink", '#fabebe'), ("Teal", '#469990'), ("Lavender", '#e6beff'),
                     ("Brown", '#9A6324'), ("Beige", '#fffac8'), ("Maroon", '#800000'), ("Mint", '#aaffc3'),
                     ("Olive", '#808000'), ("Apricot", '#ffd8b1'), ("Navy", '#000075'), ("Grey", '#a9a9a9'),
                     ("White", '#ffffff')]
startCoord = [500, 125]  # (Y, X)
endCoord = [225, 650]  # (Y, X)
listOfBots = []
numberOfBots = 20
botVisionRadius = 30
botStepSize = 10
botSlowdown = 0.06
numberOfDraws = 0
botDrawRadius = 5
paused = False
myThread = None
numRounds = 0
maxBotTurnInRads = 0.25
workingBG = None
circleQueue = queue.Queue()

class Bot:
    def __init__(self, botNumber):
        # self.colour = botPathColours[randint(0, len(botPathColours) - 1)]
        self.pathRGB = np.array([randint(50, 255), randint(50, 255), randint(50, 255), 255])
        self.pathHex = "#" + str(hex(self.pathRGB[0]))[2:] + str(hex(self.pathRGB[1]))[2:] + str(hex(self.pathRGB[2]))[2:]
        self.y = startCoord[0]
        self.x = startCoord[1]
        self.pathHistory = [(self.y, self.x)]
        self.drawingQueue = queue.Queue()
        self.number = botNumber
        self.drawCircle = 0
        self.drawCargo = 0
        self.hasSuccessfulPath = False
        self.isCarryingCargo = False
        self.pathHistoryIndex = 0
        self.direction = 2 * math.pi * random()

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
                # numRounds += 1
                shuffle(self.bots)
                for bot in self.bots:

                    # *****  LOGIC FOR EACH BOT STEP GOES HERE *****

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

                        pixelPath = self.getMovePixels(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
                        for i in range(len(pixelPath)):
                            bot.pathHistory.append(pixelPath[i])
                            bot.drawingQueue.put((pixelPath[i]) + (1,))
                        bot.y += yStep
                        bot.x += xStep



                    else:   # Bot has found destination and is transporting cargo
                        #TODO ------    Check for other bots to communicate with --------
                        for otherBot in listOfBots:
                            if bot.pathRGB != otherBot.pathRGB and (bot.x-otherBot.x)**2 + (bot.y-otherBot.y)**2 < botVisionRadius**2:

                                pass

                        # Bot is carrying cargo and is moving towards destination
                        if bot.isCarryingCargo:
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

                                    backTrackIndex = int(
                                        bot.pathHistoryIndex - (1.5 * botStepSize)) if bot.pathHistoryIndex > (
                                                1.5 * botStepSize) else 0
                                    if point in bot.pathHistory[backTrackIndex:bot.pathHistoryIndex]:
                                        continue

                                    # Look through path history in the appropriate direction and add perimeter points and their indices (in bot's path history) to a temporary list
                                    for i in range(bot.pathHistoryIndex, len(bot.pathHistory)):
                                        if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                                            pointsFoundInHistory.append((i, yPoint, xPoint))

                            # If we have found a viable shortcut, then adjust bot's path history and GUI
                            if len(pointsFoundInHistory) != 0:
                                # Determine which point provides the best shortcut (the farthest index)
                                pointsFoundInHistory.sort(key=lambda x: x[0], reverse=True)
                                bestPoint = pointsFoundInHistory[0]

                                # TODO adjust these off by ones to see if it improves "breaks" in path
                                # Draw black lines over chunk of path that is not part of shortest path
                                for i in range(bot.pathHistoryIndex, bestPoint[0]):
                                    bot.drawingQueue.put((bot.pathHistory[i]) + (0,))

                                # Add the new path to path history and add them lines to be drawn to the queue
                                newPathPixels = self.getMovePixels(bot.y, bot.x, bestPoint[1], bestPoint[2])

                                bot.pathHistory = bot.pathHistory[:bot.pathHistoryIndex] + newPathPixels + bot.pathHistory[bestPoint[0]:]
                                for point in newPathPixels:
                                    bot.drawingQueue.put(point + (1,))

                            # Go forward through path history
                            bot.pathHistoryIndex += botStepSize
                            if bot.pathHistoryIndex >= len(bot.pathHistory):
                                bot.pathHistoryIndex = len(bot.pathHistory) - 1
                                bot.isCarryingCargo = False
                            bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                            bot.x = bot.pathHistory[bot.pathHistoryIndex][1]




                        # Bot is not carrying cargo and is heading back to start
                        else:
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
                                    for i in range(bot.pathHistoryIndex, 0, -1):
                                        if bot.pathHistory[i][0] == yPoint and bot.pathHistory[i][1] == xPoint:
                                            pointsFoundInHistory.append((i, yPoint, xPoint))

                            # If we have found a viable shortcut, then adjust bot's path history and GUI
                            if len(pointsFoundInHistory) != 0:
                                # Determine which point provides the best shortcut (the farthest index)
                                pointsFoundInHistory.sort(key=lambda x: x[0])
                                bestPoint = pointsFoundInHistory[0]

                                # Draw black lines over chunk of path that is not part of shortest path
                                for i in range(bot.pathHistoryIndex, bestPoint[0], -1):
                                    bot.drawingQueue.put((bot.pathHistory[i]) + (0,))

                                # Add the new path to path history and add the lines to be drawn to the queue
                                newPathPixels = self.getMovePixels(bestPoint[1], bestPoint[2], bot.y, bot.x)

                                bot.pathHistory = bot.pathHistory[:bestPoint[0]] + newPathPixels + bot.pathHistory[bot.pathHistoryIndex:]
                                bot.pathHistoryIndex = bot.pathHistoryIndex - (bot.pathHistoryIndex - bestPoint[0]) + len(newPathPixels)
                                for point in newPathPixels:
                                    bot.drawingQueue.put(point + (1,))

                            # Go backwards through path history
                            bot.pathHistoryIndex -= botStepSize
                            if bot.pathHistoryIndex < 0:
                                bot.pathHistoryIndex = 0
                                bot.isCarryingCargo = True
                            bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                            bot.x = bot.pathHistory[bot.pathHistoryIndex][1]


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

def updateGUI(w, bots, startEndLines, numpyEnvironment):
    for bot in bots:
        q = bot.drawingQueue
        rgb = bot.pathRGB
        while not q.empty():
            p = q.get()
            if p[2] == 0:
                numpyEnvironment[p[0]][p[1]] = [0, 0, 0, 255]
            else:
                numpyEnvironment[p[0]][p[1]] = rgb

    for line in startEndLines:
        w.delete(line)
    startEndLines = drawStartEndLines(w)

    for bot in bots:
        w.delete(bot.drawCircle)
        bot.drawCircle = w.create_oval(bot.x - botDrawRadius,  bot.y - botDrawRadius, bot.x + botDrawRadius, bot.y + botDrawRadius, fill=bot.pathHex, outline=bot.pathHex)
        if bot.isCarryingCargo:
            w.delete(bot.drawCargo)
            bot.drawCargo = w.create_rectangle(bot.x - botDrawRadius - 2, bot.y - (1.5 * botDrawRadius), bot.x + botDrawRadius + 2, bot.y - (0.5 * botDrawRadius), fill='gray78', outline='gray78')

    w.pack()



def drawStartEndLines(w):
    half = 15
    start1 = w.create_line(startCoord[1] - half, startCoord[0] - half, startCoord[1] + half, startCoord[0] + half, fill='#00FF00', width=4)
    start2 = w.create_line(startCoord[1] + half, startCoord[0] - half, startCoord[1] - half, startCoord[0] + half, fill='#00FF00', width=4)
    end1 = w.create_line(endCoord[1] - half, endCoord[0] - half, endCoord[1] + half, endCoord[0] + half, fill='#e6194B', width=4)
    end2 = w.create_line(endCoord[1] + half, endCoord[0] - half, endCoord[1] - half, endCoord[0] + half, fill='#e6194B', width=4)
    return [start1, start2, end1, end2]

def clickCallback(event):
    global paused
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
    fastButton = tk.Button(root, text="Speed up", width=10, height=1, command=fasterButton)
    slowButton.pack(in_=bottomFrame, side=tk.LEFT)
    fastButton.pack(in_=bottomFrame, side=tk.LEFT)
    window.bind("<Button-1>", clickCallback)
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
        updateGUI(window, listOfBots, startEndLines, numpyEnvironment)
        window.update()
        window.delete("all")
        workingImage = ImageTk.PhotoImage(Image.fromarray(numpyEnvironment))
        window.create_image(0, 0, anchor=tk.N + tk.W, image=workingImage)
        # print("Time taken for entire update", time.time() - startTime)
