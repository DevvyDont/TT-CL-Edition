from panda3d.core import *
from . import Playground
import random

class DLPlayground(Playground.Playground):

    def __init__(self, loader, parentFSM, doneEvent):
        Playground.Playground.__init__(self, loader, parentFSM, doneEvent)

    def showPaths(self):
        from toontown.toonbase import TTLocalizer
