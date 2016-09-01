#!/usr/bin/env python3

import json
import re

isVerbose = False

def verbose(msg):
    if isVerbose:
        print(msg)

class TerminalRenderer:
    def setAnsiColor(c):
        print("\033[38;5;{}m".format(c), end="")

    def setRgbColor(r, g, b):
        print("\033[38;2;{};{};{}m".format(r, g, b), end="")

    def restoreColor():
        print("\033[0m", end="")

    def writeCharacter(c):
        print(c, end="")

    def writeNewline():
        print()

class LatexRenderer:
    def setAnsiColor(c):
        print("\\ansicolor{{{}}}".format(c), end="")

    def setRgbColor(r, g, b):
        print("\\color[RGB]{{{}, {}, {}}}".format(r, g, b), end="")

    def restoreColor():
        print("\\normalcolor{}", end="")

    def writeCharacter(c):
        # TODO: escaping
        if c == "$":
            c = "\$"
        elif c == "[" or c == "]":
            c = "{" + c + "}"
        print(c, end="")

    def writeNewline():
        print("\\\\")

class DisplayBuffer:
    OSC_regex  = r'(\x1b]|\x9d)[^\x07]*\x07'
    CSI_regex  = r'(\x1b\[|\x9b)([\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e])'
    C0_regex   = r'\x1b[\x00-\x7f]'
    text_regex = r'[\x20-\x7e]+' # TODO: utf-8

    class Cell:
        c = ' '
        color = None

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cursor_x = 0
        self.cursor_y = 0
        self.color = None

        self.contents = [[self.Cell() for x in range(width)] for y in range(height)]

    def __getitem__(self, pos):
        (x, y) = pos
        return self.contents[y][x].c

    def __setitem__(self, pos, c):
        (x, y) = pos
        self.contents[y][x].c = c
        self.contents[y][x].color = self.color

    def write(self, data):
        match = None
        while len(data) > 0:
            match = re.match(self.OSC_regex, data)
            if match:
                data = data[len(match.group(0)):]
                continue

            match = re.match(self.CSI_regex, data)
            if match:
                self.writeCsi(match.group(2))
                data = data[len(match.group(0)):]
                continue

            match = re.match(self.C0_regex, data)
            if match:
                data = data[len(match.group(0)):]
                continue

            match = re.match(self.text_regex, data)
            if match:
                self.writeText(match.group(0))
                data = data[len(match.group(0)):]
                continue

            if data[0] == "\b":
                self.writeBackspace()
            elif data[0] == "\r":
                self.writeCR()
            elif data[0] == "\n":
                self.writeLF()
            else:
                verbose("Unmatched character in input stream")

            data = data[1:len(data)]

    def writeCsi(self, sequence):
        function = sequence[-1]
        sequence = sequence[0:-1]

        if function == "m":
            return self.writeSgr(sequence)
        elif function == "J" or function == "K":
            self.erase(function, sequence)
        else:
            verbose("Unknown CSI sequence: {}".format(function))

    def writeSgr(self, sequence):
        if sequence == "0" or sequence == "":
            self.color = None
            return

        parts = re.findall(r'(\d+);?', sequence)
        parts = [int(part) for part in parts]

        i = 0
        while i < len(parts):
            if parts[i] == 0:
                self.color = None
            elif parts[i] == 1:
                pass # TODO: bold
            elif parts[i] == 4:
                pass # TODO: underline
            elif parts[i] == 7:
                pass # TODO: inverse?
            elif parts[i] == 22:
                self.color = None
            elif parts[i] == 24:
                pass # TODO: disable underline
            elif parts[i] == 27:
                pass # TODO: uninverse?
            elif parts[i] >= 30 and parts[i] <= 37:
                self.color = parts[i]-30
            elif parts[i] == 38:
                if len(parts) >= i+1 and parts[i+1] == 5:
                    self.color = parts[i+1]
                    i += 1
                elif len(parts) >= i+3:
                    self.color = (parts[i+1], parts[i+2], parts[i+3])
                    i += 3
                else:
                    verbose("Invalid color sequence")
            elif parts[i] == 39:
                self.color = None
            elif parts[i] >= 40 and parts[i] <= 47:
                pass # TODO: background colours
            elif parts[i] == 48:
                pass # TODO: background colours
            else:
                verbose("Unknown SGR: {}".format(parts[i]))

            i += 1

    def writeText(self, text):
        for c in text:
            self[self.cursor_x, self.cursor_y] = c
            self.moveCursor(1, 0)

    def writeCR(self):
        self.moveCursor(-self.cursor_x, 0)

    def writeLF(self):
        self.moveCursor(-self.cursor_x, 1)

    def writeBackspace(self):
        self.moveCursor(-1, 0)
        self[self.cursor_x, self.cursor_y] = ' '

    def moveCursor(self, dx, dy):
        self.cursor_x += dx
        if self.cursor_x >= self.width:
            self.cursor_x = 0
            dy += 1
        if self.cursor_x < 0:
            self.cursor_x = 0
        self.cursor_y += dy
        while self.cursor_y >= self.height:
            row = self.contents.pop(0)
            self.contents.append(row)
            for x in range(self.width):
                self[x, self.height-1] = ' '
            self.cursor_y -= 1

    def erase(self, function, sequence):
        if sequence == "0" or sequence == "":
            startx = self.cursor_x
            endx = self.width
            starty = self.cursor_y+1
            endy = self.height
        elif sequence == "1":
            startx = 0
            endx = self.cursor_x
            starty = 0
            endy = self.cursor_y-1
        elif sequence == "2":
            startx = 0
            endx = self.width
            starty = 0
            endy = self.height

        for x in range(startx, endx):
            self[x, self.cursor_y] = ' '

        if function == "K": # erase line
            return
        # otherwise erase screen

        for y in range(starty, endy):
            for x in range(self.width):
                self[x, y] = ' '


    def render(self, renderer):
        prevcolor = None
        for row in self.contents:
            for cell in row:
                if cell.color != prevcolor:
                    prevcolor = cell.color
                    if prevcolor is None:
                        renderer.restoreColor()
                    elif type(prevcolor) == int:
                        renderer.setAnsiColor(prevcolor)
                    else:
                        renderer.setRgbColor(*prevcolor)
                renderer.writeCharacter(cell.c)
            renderer.writeNewline()

def main(asciicast, height, timestamp):
    contents = json.loads(asciicast)

    # TODO: Use height?
    if height is None:
        height = contents["height"]

    if timestamp is None:
        timestamp = contents["duration"]

    buffer = DisplayBuffer(contents["width"], contents["height"])
    curTime = 0
    for [delay, output] in contents["stdout"]:
        curTime = curTime + delay
        if curTime >= timestamp:
            break

        buffer.write(output)

    buffer.render(LatexRenderer)

    verbose("Exported screen contents at time: {}".format(curTime))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("asciicast", nargs=1, help="An existing asciicast")
    parser.add_argument("-n", "--height", help="The number of lines to output (default: screen height)", type=int)
    parser.add_argument("-t", "--timestamp", help="The position to export the screen contents at (default: end)", type=float)
    parser.add_argument("-v", "--verbose", help="Verbose output", action="count", default=0)
    args = parser.parse_args()

    if args.verbose > 0:
        isVerbose = True

    with open(args.asciicast[0], "r") as f:
        asciicast = f.read()

    main(asciicast = asciicast, height=args.height, timestamp=args.timestamp)
