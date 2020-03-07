# Import required libraries
import math
import queue
import threading
import logging
import time
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from random import randint, shuffle, random, uniform

# Global variables and settings
botPathColours = [("Red", '#e6194B'), ("Green", '#3cb44b'), ("Yellow", '#ffe119'), ("Blue", '#4363d8'),
                     ("Orange", '#f58231'), ("Purple", '#911eb4'), ("Cyan", '#42d4f4'), ("Magenta", '#f032e6'),
                     ("Lime", '#bfef45'), ("Pink", '#fabebe'), ("Teal", '#469990'), ("Lavender", '#e6beff'),
                     ("Brown", '#9A6324'), ("Beige", '#fffac8'), ("Maroon", '#800000'), ("Mint", '#aaffc3'),
                     ("Olive", '#808000'), ("Apricot", '#ffd8b1'), ("Navy", '#000075'), ("Grey", '#a9a9a9'),
                     ("White", '#ffffff')]
startCoord = (500, 125)  # (Y, X)
endCoord = (225, 650)  # (Y, X)
listOfBots = []
numberOfBots = 200
botVisionRadius = 1000
botStepSize = 5
botSlowdown = 0.06
numberOfDraws = 0
botDrawRadius = 5
paused = False
myThread = None
numRounds = 0
maxBotTurnInRads = 0.25

class Bot:
    def __init__(self, botNumber):
        self.colour = botPathColours[randint(0, len(botPathColours) - 1)]
        self.name = self.colour[0]
        self.pathRGB = self.colour[1]
        self.y = startCoord[0]
        self.x = startCoord[1]
        self.pathHistory = [(self.y, self.x)]
        self.pathToBeDrawn = queue.Queue()
        self.number = botNumber
        self.drawCircle = 0
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
        while True:
            with self.pause_cond:
                while self.paused:
                    self.pause_cond.wait()
                numRounds += 1
                shuffle(self.bots)
                for bot in self.bots:

                    # *****  LOGIC FOR EACH BOT STEP GOES HERE *****

                    if not bot.hasSuccessfulPath:  # Bot is looking for destination
                        # Log current position
                        prevStep = (bot.y, bot.x)

                        # Check if bot can see/move to destination
                        distanceToDestination = math.sqrt((endCoord[0] - bot.y)**2 + (endCoord[1] - bot.x)**2)
                        if distanceToDestination <= botStepSize:
                            yStep = endCoord[0] - bot.y
                            xStep = endCoord[1] - bot.x
                            bot.hasSuccessfulPath = True
                            bot.pathHistoryIndex = len(bot.pathHistory) - 1
                        else:
                            if distanceToDestination <= botVisionRadius and len(self.getMovePixels(bot.y, bot.x, endCoord[0], endCoord[1])) != 0:
                                # Bot can see destination but can't reach it just yet, so it moves towards it
                                dy = endCoord[0] - bot.y
                                dx = endCoord[1] - bot.x
                                bot.direction = math.atan2(dy, dx)
                                yStep = round(math.sin(bot.direction) * botStepSize)
                                xStep = round(math.cos(bot.direction) * botStepSize)
                                pixelPath = self.getMovePixels(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
                            else:
                                pixelPath = self.generateNextBotCoordinates(bot)
                                yStep = round(math.sin(bot.direction) * botStepSize)
                                xStep = round(math.cos(bot.direction) * botStepSize)

                            for i in range(1, len(pixelPath)):
                                bot.pathHistory.append(pixelPath[i])
                        bot.y += yStep
                        bot.x += xStep
                        bot.pathToBeDrawn.put((prevStep, (bot.y, bot.x)))

                    else:   # Bot has found destination and is transporting cargo
                        if bot.isCarryingCargo:
                            # Check for other bots to communicate with
                            # Apply path smoothing
                            # Go forward through path history
                            bot.pathHistoryIndex += botStepSize
                            if bot.pathHistoryIndex >= len(bot.pathHistory):
                                bot.pathHistoryIndex = len(bot.pathHistory) - 1
                                bot.isCarryingCargo = False

                            bot.y = bot.pathHistory[bot.pathHistoryIndex][0]
                            bot.x = bot.pathHistory[bot.pathHistoryIndex][1]
                        else:
                            # Check for other bots to communicate with
                            # Apply path smoothing
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

    # Function implemented with the help of http://www.roguebasin.com/index.php?title=Bresenham%27s_Line_Algorithm
    # Checks each point in a line to ensure a bot doesn't "jump" over an illegal area
    def getMovePixels(self, currentY, currentX, futureY, futureX):
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
                if environmentCoords[coords[1]][coords[0]] == 1:
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

    def generateNextBotCoordinates(self, bot):
        failedAttempts = 0
        while True:
            maxRadians = maxBotTurnInRads + (failedAttempts * 0.05)  if 0.5 * (failedAttempts * 0.25) < 2* math.pi else 2* math.pi
            newDirection = bot.direction + uniform(-maxRadians, maxRadians)
            yStep = round(math.sin(newDirection) * botStepSize)
            xStep = round(math.cos(newDirection) * botStepSize)
            pixelPath = self.getMovePixels(bot.y, bot.x, bot.y + yStep, bot.x + xStep)
            if len(pixelPath) != 0:
                bot.direction = newDirection
                break
            failedAttempts += 1
        return pixelPath



def updateGUI(w, bots, imageDraw, startEndLines):
    for bot in bots:
        while not bot.pathToBeDrawn.empty():
            points = bot.pathToBeDrawn.get()
            start = points[0]
            end = points[1]

            # Draw line on tkinter canvas
            w.create_line(start[1], start[0], end[1], end[0], fill=bot.pathRGB)

            # Draw line on PIL Image (in memory)
            imageDraw.line([start[1], start[0], end[1], end[0]], fill=bot.pathRGB, width=1)

            global numberOfDraws
            numberOfDraws += 1

    for line in startEndLines:
        w.delete(line)
    startEndLines = drawStartEndLines(w)

    for bot in bots:
        w.delete(bot.drawCircle)
        bot.drawCircle = w.create_oval(bot.x - botDrawRadius,  bot.y - botDrawRadius, bot.x + botDrawRadius, bot.y + botDrawRadius, fill=bot.pathRGB, outline=bot.pathRGB)


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
    originalBG.save("workingBG.png")
    pixelValues = list(originalBG.getdata())
    width, height = originalBG.size
    originalBG.close()

    workingBG = Image.open("workingBG.png")
    draw = ImageDraw.Draw(workingBG)

    # Initialize tkinter tools and open window
    root = tk.Tk()
    root.title("Swarm Pathfinder")
    root.geometry("+0+5")
    window = tk.Canvas(root, width=width, height=height)
    backgroundImage = ImageTk.PhotoImage(workingBG)
    topFrame = tk.Frame(root)
    topFrame.focus_set()
    topFrame.pack(side=tk.TOP, expand=True)
    bottomFrame = tk.Frame(root)
    bottomFrame.pack(side=tk.BOTTOM)
    slowButton = tk.Button(root, text="Slow", width=10, height=1, command=slowerButton)
    fastButton = tk.Button(root, text="Fast", width=10, height=1, command=fasterButton)
    slowButton.pack(in_=bottomFrame, side=tk.LEFT)
    fastButton.pack(in_=bottomFrame, side=tk.LEFT)
    window.bind("<Button-1>", clickCallback)
    window.create_image(0, 0, anchor=tk.N + tk.W, image=backgroundImage)

    # Make a matrix for calculating where bots can and can't go (0 is free space, 1 is impassable terrain)
    environmentCoords = []
    pixelCounter = 0
    for y in range(height):
        row = []
        for x in range(width):
            value = pixelValues[pixelCounter][0] + pixelValues[pixelCounter][1] + pixelValues[pixelCounter][2]
            if value == 0:
                row.append(0)
            else:
                row.append(1)
            pixelCounter += 1
        environmentCoords.append(row)

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
        bot.drawCircle = window.create_oval(bot.x - botDrawRadius,  bot.y - botDrawRadius, bot.x + botDrawRadius, bot.y + botDrawRadius, fill=bot.pathRGB, outline=bot.pathRGB)

    startEndLines = drawStartEndLines(window)
    # Main GUI loop. Save and reload image periodically to keep tkinter from slowing down
    while True:
        # print(numRounds)
        updateGUI(window, listOfBots, draw, startEndLines)
        window.update()

        if numberOfDraws > 100:
            window.delete("all")
            startEndLines = drawStartEndLines(window)
            workingBG.save("workingBG.png")
            workingBG.close()
            workingBG = Image.open("workingBG.png")
            draw = ImageDraw.Draw(workingBG)
            workingImage = ImageTk.PhotoImage(workingBG)
            window.create_image(0, 0, anchor=tk.N + tk.W, image=workingImage)
            numberOfDraws = 0