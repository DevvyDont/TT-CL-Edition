from panda3d.core import *
from direct.interval.IntervalGlobal import *
from direct.task.TaskManagerGlobal import *
from direct.distributed.ClockDelta import *
from direct.directnotify import DirectNotifyGlobal
from . import GoonGlobals
from direct.task.Task import Task
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from toontown.coghq import DistributedCashbotBossObject, CraneLeagueGlobals
from direct.showbase import PythonUtil
from . import DistributedGoon


def _getCashbotBossGoonEmergePosHpr(h):
    x, y, z = ToontownGlobals.CashbotBossBattleThreePosHpr[:3]
    return x, y, z, h, 0, 0


class DistributedCashbotBossGoon(DistributedGoon.DistributedGoon, DistributedCashbotBossObject.DistributedCashbotBossObject):
    
    """ This is a goon that walks around in the Cashbot CFO final
    battle scene, tormenting Toons, and also providing ammo for
    defeating the boss. """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBossGoon')
    
    walkGrabZ = -3.6
    stunGrabZ = -2.2
    
    # How long does it take for a live goon to wiggle free of the magnet?
    wiggleFreeTime = 2
    
    # What happens to the crane and its cable when this object is picked up?
    craneFrictionCoef = 0.15
    craneSlideSpeed = 10
    craneRotateSpeed = 20

    def __init__(self, cr):
        DistributedCashbotBossObject.DistributedCashbotBossObject.__init__(self, cr)
        DistributedGoon.DistributedGoon.__init__(self, cr)
        
        self.target = None
        self.arrivalTime = None
        
        self.flyToMagnetSfx = loader.loadSfx('phase_5/audio/sfx/TL_rake_throw_only.ogg')
        self.hitMagnetSfx = loader.loadSfx('phase_4/audio/sfx/AA_drop_anvil_miss.ogg')
        self.toMagnetSoundInterval = Sequence(SoundInterval(self.flyToMagnetSfx, duration=ToontownGlobals.CashbotBossToMagnetTime, node=self), SoundInterval(self.hitMagnetSfx, node=self))
        self.hitFloorSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_flowerpot.ogg')
        self.hitFloorSoundInterval = SoundInterval(self.hitFloorSfx, duration=1.0, node=self)
        self.wiggleSfx = loader.loadSfx('phase_5/audio/sfx/SA_finger_wag.ogg')
        self.name = 'goon'
        return

    def _doDebug(self, _=None):
        self.boss.goonStatesDebug(doId=self.doId, content='(Client) state change %s ---> %s' % (self.oldState, self.newState))

    def generate(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.generate(self)
        DistributedGoon.DistributedGoon.generate(self)

    def announceGenerate(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.announceGenerate(self)

        # It is important to call setupPhysics() before we call
        # DistributedGoon.announceGenerate(), since setupPhysics()
        # will reassign our NodePath and thereby invalidate any
        # messenger hooks already added.  In fact, it is important
        # that we not have any outstanding messenger hooks at the time
        # we call setupPhysics().
        self.setupPhysics('goon')
        
        DistributedGoon.DistributedGoon.announceGenerate(self)
        
        self.name = 'goon-%s' % self.doId
        self.setName(self.name)
        
        self.setTag('doId', str(self.doId))
        self.collisionNode.setName('goon')
        cs = CollisionSphere(0, 0, 4, 4) #TTR Collisions
        #cs = CollisionCapsule(0, 0, 4, 0, 0, 4, 4) #TTCC Collisions
        self.collisionNode.addSolid(cs)
        self.collisionNode.setIntoCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CashbotBossObjectBitmask)
        
        self.wiggleTaskName = self.uniqueName('wiggleTask')
        self.wiggleFreeName = self.uniqueName('wiggleFree')
        self._pendingStunRecovery = 0
        
        self.boss.goons.append(self)
        
        self.reparentTo(render)

    def disable(self):
        if self in self.boss.goons:
            i = self.boss.goons.index(self)
            del self.boss.goons[i]
        DistributedGoon.DistributedGoon.disable(self)
        DistributedCashbotBossObject.DistributedCashbotBossObject.disable(self)

    def delete(self):
        DistributedGoon.DistributedGoon.delete(self)
        DistributedCashbotBossObject.DistributedCashbotBossObject.delete(self)

    def hideShadows(self):
        self.dropShadow.hide()

    def showShadows(self):
        self.dropShadow.show()

    def getMinImpact(self):
        # This method returns the minimum impact, in feet per second,
        # with which the object should hit the boss before we bother
        # to tell the server.
        return self.boss.ruleset.MIN_GOON_IMPACT

    def doHitBoss(self, impact, craneId):
        self.d_hitBoss(impact, craneId)

        if impact >= self.getMinImpact():
            self.b_destroyGoon()

    def __startWalk(self):
        # Generate an interval to walk the goon to his target square
        # by the specified time.
        self.__stopWalk()
        
        if self.target:
            now = globalClock.getFrameTime()
            availableTime = self.arrivalTime - now
            if availableTime > 0:
                # How long will it take to rotate to position?
                origH = self.getH()
                h = PythonUtil.fitDestAngle2Src(origH, self.targetH)
                delta = abs(h - origH)
                turnTime = delta / (self.velocity * 5)
                
                # And how long will it take to walk to position?
                dist = Vec3(self.target - self.getPos()).length()
                walkTime = dist / self.velocity
                
                denom = turnTime + walkTime
                if denom != 0:
                    # Fit that within our available time.
                    timeCompress = availableTime / denom
                    self.walkTrack = Sequence(self.hprInterval(turnTime * timeCompress, VBase3(h, 0, 0)), self.posInterval(walkTime * timeCompress, self.target))
                    self.walkTrack.start()
            else:
                self.setPos(self.target)
                self.setH(self.targetH)

    def __stopWalk(self):
        # Stop the walk interval.
        if self.walkTrack:
            self.walkTrack.pause()
            self.walkTrack = None
        return

    def __wiggleTask(self, task):
        # If the unfortunate player picks up an active goon, the
        # magnet should wiggle erratically to indicate instability.
        elapsed = globalClock.getFrameTime() - self.wiggleStart
        h = math.sin(elapsed * 17) * 5
        p = math.sin(elapsed * 29) * 10
        if self.crane:
            self.crane.wiggleMagnet.setHpr(h, p, 0)
        return Task.cont

    def __wiggleFree(self, task):
        # We've successfully wiggled free after being picked up.
        if self.crane:
            self.crane.releaseObject()
        
        # And we can't be picked up again until we land.
        self.stashCollisions()
        return Task.done

    def fellOut(self):
        # The goon fell out of the world. Just destroy him and move on.
        self.b_destroyGoon()

    def handleToonDetect(self, collEntry = None):
        if self.boss.localToonIsSafe:
            return
        DistributedGoon.DistributedGoon.handleToonDetect(self, collEntry)

    def prepareGrab(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.prepareGrab(self)
        self.__stopWalk()
        if self.isStunned:
            self.pose('collapse', 48)
            self.grabPos = (0, 0, self.stunGrabZ * self.scale)
        else:
            # He's got a live one!
            self.setPlayRate(4, 'walk')
            self.loop('walk')
            self.grabPos = (0, 0, self.walkGrabZ * self.scale)
            self.wiggleStart = globalClock.getFrameTime()
            taskMgr.add(self.__wiggleTask, self.wiggleTaskName)
            base.sfxPlayer.playSfx(self.wiggleSfx, node=self)
            if self.avId == localAvatar.doId:
                taskMgr.doMethodLater(self.wiggleFreeTime, self.__wiggleFree, self.wiggleFreeName)
        self.radar.hide()

    def __lerpToGrabPos(self):
        if not self.crane or self.crane.gripper.isEmpty():
            return
        if self.lerpInterval:
            self.lerpInterval.finish()
        self.lerpInterval = Parallel(
            self.posInterval(ToontownGlobals.CashbotBossToMagnetTime, Point3(*self.grabPos)),
            self.quatInterval(ToontownGlobals.CashbotBossToMagnetTime, VBase3(self.getH(), 0, 0)),
            self.toMagnetSoundInterval)
        self.lerpInterval.start()

    def __applyStunOnMagnet(self):
        # Live goon stunned while already on the magnet: swap to collapse
        # and re-lerp to the stunned attach point without a full regrab.
        self.isStunned = 1
        self.__stopWalk()
        self.stop()
        if self.radar:
            self.radar.hide()
        if self.animTrack:
            self.animTrack.finish()
            self.animTrack = None
        taskMgr.remove(self.wiggleTaskName)
        taskMgr.remove(self.wiggleFreeName)
        if self.crane:
            self.crane.wiggleMagnet.setHpr(0, 0, 0)
        self.pose('collapse', 48)
        self.grabPos = (0, 0, self.stunGrabZ * self.scale)
        self.__lerpToGrabPos()
        base.playSfx(self.collapseSound, node=self)

    def prepareRelease(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.prepareRelease(self)
        if self.crane:
            self.crane.wiggleMagnet.setHpr(0, 0, 0)
        taskMgr.remove(self.wiggleTaskName)
        taskMgr.remove(self.wiggleFreeName)
        self.setPlayRate(self.animMultiplier, 'walk')

    def __applyStunnedOverlay(self, ts=0):
        # Stunned while grabbed or falling: keep crane physics, swap visuals.
        self.isStunned = 1
        self.__stopWalk()
        if self.radar:
            self.radar.hide()
        if self.animTrack:
            self.animTrack.finish()
            self.animTrack = None

        if self.state in ('Dropped', 'LocalDropped', 'SlidingFloor'):
            self.pose('collapse', 48)
            base.playSfx(self.collapseSound, node=self)
            return

        if self.state in ('Grabbed', 'LocalGrabbed'):
            self.__applyStunOnMagnet()
            return

        if self.state != 'Stunned':
            self.demand('Stunned', ts)

    def __resumeAfterCraneDrop(self):
        # Only apply deferred recovery that was blocked during flight.
        # Stunned/Walk transitions after landing are server-authoritative.
        if getattr(self, '_pendingStunRecovery', False):
            self._pendingStunRecovery = False
            if self.state != 'Recovery':
                self.demand('Recovery')
        
    ##### Messages To/From The Server #####

    def setObjectState(self, state, avId, craneId):
        if craneId:
            self.crane = self.cr.doId2do.get(craneId)
        if state in ('W', 'a', 'b', 'B'):
            if self.isInCraneInteractionState():
                return
        if state == 'S':
            if self.isInCraneInteractionState():
                if not self.isStunned:
                    self.__applyStunnedOverlay()
                return
            if self.isStunned:
                return
            if self.state != 'Stunned':
                self.demand('Stunned')
        elif state == 'W':
            if self.isInCraneInteractionState():
                return
            self.demand('Walk')
        elif state == 'B':
            if self.state != 'Battle':
                self.demand('Battle')
        elif state == 'R':
            if self.isInCraneInteractionState():
                if self.isStunned:
                    self._pendingStunRecovery = True
                return
            if self.state != 'Recovery':
                self.demand('Recovery')
        elif state == 'a':
            self.demand('EmergeA')
        elif state == 'b':
            self.demand('EmergeB')
        else:
            DistributedCashbotBossObject.DistributedCashbotBossObject.setObjectState(self, state, avId, craneId)

    def setTarget(self, x, y, h, arrivalTime):
        self.target = Point3(x, y, 0)
        self.targetH = h
        now = globalClock.getFrameTime()
        self.arrivalTime = globalClockDelta.networkToLocalTime(arrivalTime, now)
        if self.state == 'Walk':
            self.__startWalk()

    def d_destroyGoon(self):
        self.sendUpdate('destroyGoon')

    def b_destroyGoon(self):
        if not self.isDead:
            self.d_destroyGoon()
            self.destroyGoon()

    def destroyGoon(self):
        if not self.isDead:
            self.playCrushMovie(None, None)
        self.resetClientBroadcastState()
        self.isStunned = 0
        self._pendingStunRecovery = 0
        taskMgr.remove(self.wiggleTaskName)
        taskMgr.remove(self.wiggleFreeName)
        self.demand('Off')
        if self in self.boss.goons:
            self.boss.goons.remove(self)
        return

    def __snapToEmergeSpawn(self, h):
        self._setPosHprLocal(*_getCashbotBossGoonEmergePosHpr(h))
        
    ### FSM States ###

    def enterOff(self):
        DistributedGoon.DistributedGoon.enterOff(self)
        DistributedCashbotBossObject.DistributedCashbotBossObject.enterOff(self)

    def exitOff(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.exitOff(self)
        DistributedGoon.DistributedGoon.exitOff(self)

    def enterWalk(self, avId = None, ts = 0):
        self._pendingStunRecovery = 0
        self.startToonDetect()
        self.isStunned = 0
        self.__startWalk()
        self.loop('walk', 0)
        self.unstashCollisions()

    def exitWalk(self):
        self.__stopWalk()
        self.stopToonDetect()
        self.stop()

    def enterEmergeA(self):
        # The goon emerges from door a.
        self.resetClientBroadcastState()
        self.isStunned = 0
        self._pendingStunRecovery = 0
        self.undead()
        self.reparentTo(render)
        self.__snapToEmergeSpawn(0)
        self.stopToonDetect()
        self.boss.doorA.request('open')
        self.radar.hide()
        self.__startWalk()
        self.loop('walk', 0)
        if self not in self.boss.goons:
            self.boss.goons.append(self)

    def exitEmergeA(self):
        if self.boss.doorA:
            self.boss.doorA.request('close')
        self.radar.show()
        self.__stopWalk()

    def enterEmergeB(self):
        # The goon emerges from door b.
        self.resetClientBroadcastState()
        self.isStunned = 0
        self._pendingStunRecovery = 0
        self.undead()
        self.reparentTo(render)
        self.__snapToEmergeSpawn(180)
        self.stopToonDetect()
        self.boss.doorB.request('open')
        self.radar.hide()
        self.__startWalk()
        self.loop('walk', 0)
        if self not in self.boss.goons:
            self.boss.goons.append(self)

    def exitEmergeB(self):
        if self.boss.doorB:
            self.boss.doorB.request('close')
        self.radar.show()
        self.__stopWalk()

    def enterBattle(self, avId = None, ts = 0):
        DistributedGoon.DistributedGoon.enterBattle(self, avId, ts)
        avatar = base.cr.doId2do.get(avId)
        if avatar:
            # Make the toon flash, and knock him off the crane.
            messenger.send('exitCrane')
            avatar.stunToon()
        self.unstashCollisions()

    def enterStunned(self, ts = 0):
        DistributedGoon.DistributedGoon.enterStunned(self, ts)
        self.unstashCollisions()

    def enterRecovery(self, ts = 0, pauseTime = 0):
        DistributedGoon.DistributedGoon.enterRecovery(self, ts, pauseTime)
        self.isStunned = 0
        self.unstashCollisions()

    def recoveryDone(self, pauseTime):
        # Walk after recovery is driven by the server's broadcast W.
        return Task.done

    def enterFree(self):
        DistributedCashbotBossObject.DistributedCashbotBossObject.enterFree(self)
        self.__resumeAfterCraneDrop()

    def d_requestWalk(self):
        self.sendUpdate('requestWalk')
