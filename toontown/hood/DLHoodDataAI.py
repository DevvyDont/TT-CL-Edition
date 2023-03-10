from direct.directnotify import DirectNotifyGlobal
import HoodDataAI
from toontown.toonbase import ToontownGlobals
from toontown.safezone import DLTreasurePlannerAI
from toontown.safezone import ButterflyGlobals

class DLHoodDataAI(HoodDataAI.HoodDataAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DLHoodDataAI')

    def __init__(self, air, zoneId=None):
        hoodId = ToontownGlobals.DonaldsDreamland
        if zoneId == None:
            zoneId = hoodId
        HoodDataAI.HoodDataAI.__init__(self, air, zoneId, hoodId)
        return

    def startup(self):
        HoodDataAI.HoodDataAI.startup(self)
        self.treasurePlanner = DLTreasurePlannerAI.DLTreasurePlannerAI(self.zoneId)
        self.treasurePlanner.start()
