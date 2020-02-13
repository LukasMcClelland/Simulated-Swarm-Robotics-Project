# Import required libraries
import queue
import threading
import logging
import time

from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from random import randint

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
numberOfBots = 1
botVisionRadius = 0
botStepSize = 100
botSlowdown = 0.1
guiCounter = 0
numberOfDraws = 0
botDrawRadius = 3
botCircles = []
threads = list()
threadEvents = list()
paused = False

class Bot:
    def __init__(self, botNumber):
        self.colour = botPathColours[randint(0, len(botPathColours) - 1)]
        self.name = self.colour[0]
        self.pathRGB = self.colour[1]
        self.pathHistory = []
        self.y = startCoord[0]
        self.x = startCoord[1]
        self.pathToBeDrawn = queue.Queue()
        self.number = botNumber
        self.drawCircle = 0

# Function implemented with the help of http://www.roguebasin.com/index.php?title=Bresenham%27s_Line_Algorithm
# Checks each point in a line to ensure a bot doesn't "jump" over an illegal area
def validMove(currentY, currentX, futureY, futureX):
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
        for x in range(currentX, futureX + 1):
            coords = (x, y)
            if lineIsSteep:
                coords = (y, x)
            if environmentCoords[coords[1]][coords[0]] == 1:
                return False
            e -= abs(dy)
            if e < 0:
                y += yStep
                e += dx
        return True

    else:
        return False

def threadFunction(number, event):
    # Initialize bot
    logger.info("Thread %s: starting", number)
    bot = Bot(number)
    listOfBots.append(bot)

    # Main bot loop
    while True:
        # if

        logger.info("Thread %s: stepping", number)
        while True:
            yStep = randint(-botStepSize, botStepSize)
            xStep = randint(-botStepSize, botStepSize)
            if validMove(bot.y, bot.x, bot.y + yStep, bot.x + xStep):
                break
        prevStep = (bot.y, bot.x)
        bot.pathHistory.append(prevStep)
        bot.y += yStep
        bot.x += xStep
        bot.pathToBeDrawn.put((prevStep, (bot.y, bot.x)))
        time.sleep(botSlowdown)

    # Logging and cleanup
    # logger.info("Thread %s: finishing", name)


def updateGUI(w, bots, imageDraw):
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

        w.delete(bot.drawCircle)
        bot.drawCircle = w.create_oval(bot.x - botDrawRadius,  bot.y - botDrawRadius, bot.x + botDrawRadius, bot.y + botDrawRadius, fill=bot.pathRGB, outline=bot.pathRGB)
    w.pack()

def clickCallback(event):
    if not paused:
        for e in threadEvents:
            e.clear()
    else:
        for e in threadEvents:
            e.set()

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
    window = tk.Canvas(root, width=width, height=height)
    backgroundImage = ImageTk.PhotoImage(workingBG)
    frame = tk.Frame(root)
    frame.focus_set()
    frame.pack()
    window.bind("<Button-1>", clickCallback)
    window.create_image(0, 0, anchor=tk.N + tk.W, image=backgroundImage)
    updateGUI(window, listOfBots, draw)
    window.update()

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


    # Launch threads
    print("Starting threads")
    threads = list()
    for index in range(numberOfBots):
        logging.info("Main    : create and start thread %d.", index)
        e = threading.Event()
        x = threading.Thread(target=threadFunction, args=(index,e,))
        threadEvents.append(e)
        threads.append(x)
        x.start()
    print("Done starting threads")

    # Draw initial bot positions
    for bot in listOfBots:
        bot.drawCircle = window.create_oval(bot.x - botDrawRadius, bot.y - botDrawRadius, bot.x + botDrawRadius, bot.y + botDrawRadius, fill=bot.pathRGB)


    # Main GUI loop. Save and reload image periodically to keep tkinter from slowing down
    while True:
        updateGUI(window, listOfBots, draw)
        window.update()
        # print("Draws = ", numberOfDraws)

        if numberOfDraws > 1000:
            window.delete("all")
            workingBG.save("workingBG.png")
            workingBG.close()
            workingBG = Image.open("workingBG.png")
            draw = ImageDraw.Draw(workingBG)
            workingImage = ImageTk.PhotoImage(workingBG)
            window.create_image(0, 0, anchor=tk.N + tk.W, image=workingImage)
            numberOfDraws = 0


