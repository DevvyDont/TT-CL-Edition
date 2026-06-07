from panda3d.core import *
from panda3d.physics import *
from direct.interval.IntervalGlobal import *
from direct.directnotify import DirectNotifyGlobal
from direct.distributed import DistributedSmoothNode
from toontown.coghq import CraneLeagueGlobals
from toontown.toonbase import ToontownGlobals
from otp.otpbase import OTPGlobals
from direct.fsm import FSM
from direct.task import Task
import math
import copy
smileyDoId = 1

class DistributedCashbotBossObject(DistributedSmoothNode.DistributedSmoothNode, FSM.FSM):

    """ This is an object that can be picked up an dropped in the
    final battle scene with the Cashbot CFO.  In particular, it's a
    safe or a goon.  """
    
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedCashbotBossObject')

    # This should be true for objects that will eventually transition
    # from SlidingFloor to Free when they stop moving.
    wantsWatchDrift = 1

    # Number of recent frames to determine the pre-collision velocity
    velocityHistoryLen = 6

    def __init__(self, cr):
        DistributedSmoothNode.DistributedSmoothNode.__init__(self, cr)
        FSM.FSM.__init__(self, 'DistributedCashbotBossObject')
        
        self.boss = None
        self.avId = 0
        self.craneId = 0
        self.cleanedUp = 0
            
        # A CollisionNode to keep me out of walls and floors, and to
        # keep others from bumping into me.  We use PieBitmask instead
        # of WallBitmask, to protect against objects (like goons)
        # self-colliding.
        self.collisionNode = CollisionNode('object')
        self.collisionNode.setIntoCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.WallBitmask | ToontownGlobals.CashbotBossObjectBitmask | OTPGlobals.CameraBitmask)
        self.collisionNode.setFromCollideMask(ToontownGlobals.PieBitmask | OTPGlobals.FloorBitmask)
        self.collisionNodePath = NodePath(self.collisionNode)
        
        self.physicsActivated = 0

        self.toMagnetSoundInterval = Sequence()
        self.hitFloorSoundInterval = Sequence()
        
        # A solid sound for when we get a good hit on the boss.
        self.hitBossSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_safe_miss.ogg')
        self.hitBossSoundInterval = SoundInterval(self.hitBossSfx)
        
        # A squishy sound for when we hit the boss, but not hard enough.
        self.touchedBossSfx = loader.loadSfx('phase_5/audio/sfx/AA_drop_sandbag.ogg')
        self.touchedBossSoundInterval = SoundInterval(self.touchedBossSfx, duration=0.8)
        
        # Cranes will fill in this with the interval to lerp the
        # object to the crane.
        self.lerpInterval = None
        self.awaitingGrabConfirm = False
        
        self.setBroadcastStateChanges(True)
        self.accept(self.getStateChangeEvent(), self._doDebug)

    def _doDebug(self, _=None):
        pass

    CRANE_INTERACTION_STATES = (
        'LocalGrabbed', 'LocalDropped', 'Grabbed', 'Dropped', 'SlidingFloor')

    def isInCraneInteractionState(self):
        return self.state in self.CRANE_INTERACTION_STATES

    def isInLocalCraneState(self):
        return self.state in ('LocalGrabbed', 'LocalDropped')

    def _ignoreIncomingSmooth(self):
        if getattr(self, '_applyingLocalPos', False):
            return False
        if self.localControl:
            return True
        if self.state in ('LocalGrabbed', 'Grabbed'):
            return True
        crane = getattr(self, 'crane', None)
        if crane and crane.gripper and not crane.gripper.isEmpty():
            if self.getParent().compareTo(crane.gripper) == 0:
                return True
        return False

    def _setPosHprLocal(self, *args):
        self._applyingLocalPos = True
        try:
            NodePath.setPosHpr(self, *args)
        finally:
            self._applyingLocalPos = False

    def setPosHpr(self, x, y, z, h, p=0, r=0):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setPosHpr(self, x, y, z, h, p, r)

    def setX(self, x):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setX(self, x)

    def setY(self, y):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setY(self, y)

    def setZ(self, z):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setZ(self, z)

    def setH(self, h):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setH(self, h)

    def setP(self, p):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setP(self, p)

    def setR(self, r):
        if self._ignoreIncomingSmooth():
            return
        NodePath.setR(self, r)

    def b_clearSmoothing(self):
        self.d_clearSmoothing()
        self.smoother.clearPositions(0)

    def d_clearSmoothing(self):
        self.sendUpdate('clearSmoothing', [0])

    def setComponentX(self, x):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentX(self, x)

    def setComponentY(self, y):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentY(self, y)

    def setComponentZ(self, z):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentZ(self, z)

    def setComponentH(self, h):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentH(self, h)

    def setComponentP(self, p):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentP(self, p)

    def setComponentR(self, r):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentR(self, r)

    def setComponentL(self, l):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentL(self, l)

    def setComponentT(self, timestamp):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentT(self, timestamp)

    def setComponentTLive(self, timestamp):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.setComponentTLive(self, timestamp)

    def smoothPosition(self):
        if self._ignoreIncomingSmooth():
            return
        DistributedSmoothNode.DistributedSmoothNode.smoothPosition(self)

    def resetClientBroadcastState(self):
        self.localControl = False
        self.awaitingGrabConfirm = False
        self.stopPosHprBroadcast()
        self.stopSmooth()
        self.smoother.clearPositions(0)
        if self.physicsActivated:
            self.deactivatePhysics()
        if hasattr(self, 'physicsObject'):
            self.physicsObject.setVelocity(0, 0, 0)
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None

    def disable(self):
        self.cleanup()
        self.stopSmooth()
        DistributedSmoothNode.DistributedSmoothNode.disable(self)

    def cleanup(self):
        # is this being called twice?
        if self.cleanedUp:
            return
        else:
            self.cleanedUp = 1
            
        self.demand('Off')
        self.detachNode()
        
        self.toMagnetSoundInterval.finish()
        self.hitFloorSoundInterval.finish()
        self.hitBossSoundInterval.finish()
        self.touchedBossSoundInterval.finish()
        del self.toMagnetSoundInterval
        del self.hitFloorSoundInterval
        del self.hitBossSoundInterval
        del self.touchedBossSoundInterval
        
        self.boss = None
        return

    def setupPhysics(self, name):
        an = ActorNode('%s-%s' % (name, self.doId))
        anp = NodePath(an)
        if not self.isEmpty():
            self.reparentTo(anp)

        # It is important that there be no messenger hooks added on
        # this object at the time we reassign the NodePath.
        NodePath.assign(self, anp)
        
        self.physicsObject = an.getPhysicsObject()
        self.setTag('object', str(self.doId))
       
        self.collisionNodePath.reparentTo(self)
        self.handler = PhysicsCollisionHandler()
        self.handler.addCollider(self.collisionNodePath, self)

        # Set up a collision event so we know when the object hits the
        # floor, or the boss's target.
        self.collideName = self.uniqueName('collide')
        self.handler.addInPattern(self.collideName + '-%in')
        self.handler.addAgainPattern(self.collideName + '-%in')
        
        self.watchDriftName = self.uniqueName('watchDrift')
        self.recordVelName = self.uniqueName('recordVel')

        # Disable RespectPrevTransform
        #base.cTrav.setRespectPrevTransform(False)

    def activatePhysics(self):
        if not self.physicsActivated:
            self.boss.physicsMgr.attachPhysicalNode(self.node())
            base.cTrav.addCollider(self.collisionNodePath, self.handler)
            self.physicsActivated = 1

            # Cache the velocity history while physics is active.
            self.velocityHistory = []
            taskMgr.add(self.__recordVelocity, self.recordVelName)

            self.accept(self.collideName + '-floor', self.__hitFloor)
            self.accept(self.collideName + '-goon', self.__hitGoon)
            self.acceptOnce(self.collideName + '-headTarget', self.__hitBoss)
            self.accept(self.collideName + '-dropPlane', self.__hitDropPlane)

    def deactivatePhysics(self):
        if self.physicsActivated:
            self.boss.physicsMgr.removePhysicalNode(self.node())
            base.cTrav.removeCollider(self.collisionNodePath)
            self.physicsActivated = 0

            taskMgr.remove(self.recordVelName)

            self.ignore(self.collideName + '-floor')
            self.ignore(self.collideName + '-goon')
            self.ignore(self.collideName + '-headTarget')
            self.ignore(self.collideName + '-dropPlane')

    def hideShadows(self):
        pass

    def showShadows(self):
        pass

    def stashCollisions(self):
        self.collisionNodePath.stash()

    def unstashCollisions(self):
        self.collisionNodePath.unstash()

    def __hitFloor(self, entry):
        if self.state == 'Dropped' or self.state == 'LocalDropped':
            self.d_hitFloor()
            self.demand('SlidingFloor', localAvatar.doId)

    def __hitGoon(self, entry):
        if self.state == 'Dropped' or self.state == 'LocalDropped':
            goonId = int(entry.getIntoNodePath().getNetTag('doId'))
            goon = self.cr.doId2do.get(goonId)
            if goon:
                self.doHitGoon(goon)

    def doHitGoon(self, goon):
        # Override in a derived class to do something if the object is
        # dropped on a goon.
        pass

    def __recordVelocity(self, task):
        # The PhysicsCollisionHandler overwrites the realtime velocity with
        # a slower, deflected one the instant the object touches the boss, and
        # this happens BEFORE the headTarget collision event reaches __hitBoss().
        # Therefore, we must keep track of the velocity before the collision.
        self.velocityHistory.append(self.physicsObject.getVelocity())
        if len(self.velocityHistory) > self.velocityHistoryLen:
            del self.velocityHistory[0]
        return Task.cont

    def __getApproachVelocity(self):
        # Return the best pre-collision velocity in the sample. This makes
        # impact depend on how the object was actually travelling without
        # also depending on the object's H (heading) value which caused
        # different post-collision behavior for different H values
        best = self.physicsObject.getVelocity()
        bestLenSq = best.lengthSquared()
        for vel in self.velocityHistory:
            lenSq = vel.lengthSquared()
            if lenSq > bestLenSq:
                best = vel
                bestLenSq = lenSq
        return best

    def __hitBoss(self, entry):
        if (self.state == 'Dropped' or self.state == 'LocalDropped') and self.craneId != self.boss.doId:

            # Use the pre-col velocity rather than the post-col
            # velocity. At this point, the PhysicsCollisionHandler has already
            # replaced the post-col velocity, whose direction depends on
            # WHERE we struck and the orientation of the object
            # travelling.
            vel = self.__getApproachVelocity()
            # Nevermind, we are returning to monke
            vel = self.physicsObject.getVelocity()
            # Re-express it in the crane's frame, whose +Y axis points from the
            # crane out toward the boss.
            vel = self.crane.root.getRelativeVector(render, vel)
            # Throw away the magnitude so that only the DIRECTION remains.
            # Impact is how much of that unit direction points at the boss.
            vel.normalize()
            impact = vel[1]

            if impact >= self.getMinImpact():
                print('hit! %s' % impact)
                self.hitBossSoundInterval.start()
                self.doHitBoss(impact, self.craneId)
            else:
                self.touchedBossSoundInterval.start()
                print('--not hard enough: %s' % impact)

    def doHitBoss(self, impact, craneId):
        # Derived classes can override this to do something specific
        # when we successfully hit the boss.
        self.d_hitBoss(impact, craneId)

    def __hitDropPlane(self, entry):
        self.notify.info('%s fell out of the world.' % self.doId)
        self.fellOut()

    def fellOut(self):
        # Override in a derived class to do the right thing when the
        # object falls out of the world.
        raise Exception('fellOut unimplented')

    def getMinImpact(self):
        # This method returns the minimum impact, in feet per second,
        # with which the object should hit the boss before we bother
        # to tell the server.
        return 0

    def __watchDrift(self, task):
        if self.state != 'SlidingFloor':
            return Task.done

        # Checks the object for non-zero velocity.  When the velocity
        # reaches zero in the XY plane, we tell the AI we're done
        # moving it around.
        v = self.physicsObject.getVelocity()
        
        if abs(v[0]) < 0.0001 and abs(v[1]) < 0.0001:
            self.d_requestFree()
            self.demand('Free')
            
        return Task.cont

    def prepareGrab(self):
        # Stop stale posHpr broadcasts from fighting the grab reparent.
        # At high ping, late setComponent* / setPosHpr from a previous slide
        # can teleport the object before wrtReparentTo(gripper).
        self.stopPosHprBroadcast()
        if self.physicsActivated:
            self.deactivatePhysics()
        if hasattr(self, 'physicsObject'):
            self.physicsObject.setVelocity(0, 0, 0)

        isLocal = (self.avId == base.localAvatar.doId)
        self.localControl = isLocal

        self._applyingLocalPos = True
        try:
            worldMat = self.getTransform(render)
            NodePath.wrtReparentTo(self, render)
            self.setTransform(render, worldMat)
            if isLocal:
                self.b_clearSmoothing()
            else:
                self.stopSmooth()
                self.b_clearSmoothing()
        finally:
            self._applyingLocalPos = False

    def prepareRelease(self):
        self.localControl = False


        
    ##### Messages To/From The Server #####

    def setBossCogId(self, bossCogId):
        self.bossCogId = bossCogId

        # This would be risky if we had toons entering the zone during
        # a battle--but since all the toons are always there from the
        # beginning, we can be confident that the BossCog has already
        # been generated by the time we receive the generate for its
        # associated objects.
        self.boss = base.cr.doId2do[bossCogId]

    def __isPendingGrabFor(self, avId, craneId):
        return (self.awaitingGrabConfirm and avId == base.localAvatar.doId and
                craneId == self.craneId)

    def __acknowledgePendingGrab(self, avId, craneId):
        # Grab confirmed after we already optimistically dropped/slid.
        self.awaitingGrabConfirm = False
        self.avId = avId
        self.craneId = craneId
        self.localControl = (avId == base.localAvatar.doId)
        if self.state == 'LocalDropped':
            self.startPosHprBroadcast()
        elif self.state == 'Free':
            self.avId = 0
            self.craneId = 0
            self.localControl = False

    def setObjectState(self, state, avId, craneId):
        if self.state == 'Off':
            return

        if state == 'G':
            if self.__isPendingGrabFor(avId, craneId):
                if self.state in ('LocalDropped', 'SlidingFloor', 'Free'):
                    self.__acknowledgePendingGrab(avId, craneId)
                    return
            if self.state == 'LocalDropped':
                if avId == base.localAvatar.doId:
                    # Our own late grab confirm after an optimistic drop.
                    return
                # Another player snatched it while we still own the fall locally.
                self.awaitingGrabConfirm = False
                self.demand('Grabbed', avId, craneId)
                return
            if self.state in ('SlidingFloor', 'Free') and avId == base.localAvatar.doId:
                # Already dropped locally; ignore a late grab confirm.
                return
            if (self.state == 'Grabbed' and self.avId == avId and
                    self.craneId == craneId):
                return
            self.demand('Grabbed', avId, craneId)
        elif state == 'D':
            if self.state in ('LocalDropped', 'SlidingFloor', 'Free'):
                return
            if self.state != 'Dropped':
                self.demand('Dropped', avId, craneId)
        elif state == 's':
            if self.isInCraneInteractionState():
                return
            if self.state != 'SlidingFloor':
                self.demand('SlidingFloor', avId)
        elif state == 'F':
            if self.isInLocalCraneState():
                return
            if self.state in ('LocalGrabbed', 'Grabbed'):
                return
            if self.state == 'LocalDropped':
                return
            if (self.avId == base.localAvatar.doId and
                    self.state in ('Dropped', 'SlidingFloor')):
                if self.wantsWatchDrift:
                    # Local goon owner transitions to Free via __watchDrift.
                    return
                # Safes (wantsWatchDrift=0) stay under local slide control.
                return
            self.demand('Free')
        else:
            self.notify.error('Invalid state from AI: %s' % state)
            
    def __getCraneAndObject(self, avId):
        if self.boss and self.boss.cranes != None:
            for crane in self.boss.cranes.values():
                if crane.avId == avId:
                    return (crane.doId, self.doId)

        return (0, 0)

    def d_requestGrab(self):
        self.sendUpdate('requestGrab')

    def rejectGrab(self):
        # The server tells us we can't have it for whatever reason.
        if (self.state in ('LocalGrabbed', 'LocalDropped', 'SlidingFloor', 'Free') or
                self.awaitingGrabConfirm):
            self.awaitingGrabConfirm = False
            self.demand('Free')

    def d_requestDrop(self):
        self.sendUpdate('requestDrop')

    def d_hitFloor(self):
        self.sendUpdate('hitFloor')

    def d_requestFree(self):
        self.sendUpdate('requestFree', [self.getX(),
         self.getY(),
         self.getZ(),
         self.getH()])

    def d_hitBoss(self, impact, craneId):
        self.sendUpdate('hitBoss', [impact, craneId])

    def defaultFilter(self, request, args):
        # We overload the default filter function to disallow *any*
        # state transitions after the object has been disabled or
        # deleted, or before it has been fully generated.
        if self.boss == None:
            raise FSM.RequestDenied(request)
            
        return FSM.FSM.defaultFilter(self, request, args)



    ### FSM States ###

    def enterOff(self):
        # In state Off, the object is not parented to the scene graph.
        # In all other states, it is.
        self.detachNode()
        
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
        return

    def exitOff(self):
        self.reparentTo(render)

    def enterLocalGrabbed(self, avId, craneId):
        # This state is like Grabbed, except that it is only triggered
        # locally.  In this state, we have requested a grab, and we
        # will act as if we have grabbed the object successfully, but
        # we have not yet heard confirmation from the AI so we might
        # later discover that we didn't grab it after all.
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)
        self.localControl = True
        self.hideShadows()
        self.prepareGrab()
        if self.crane:
            self.crane.grabObject(self)

    def exitLocalGrabbed(self):
        if self.newState != 'Grabbed':
            if self.crane:
                self.crane.dropObject(self)
            self.prepareRelease()
            del self.crane
            self.showShadows()

    def enterGrabbed(self, avId, craneId):
        # Grabbed by a crane, or by the boss for a helmet.  craneId is
        # the doId of the crane or the doId of the boss himself.

        if self.oldState == 'LocalGrabbed':
            if craneId == self.craneId:
                # This is just the confirmation from the AI that we
                # did, in fact, grab this object with the expected
                # crane; we don't need to do anything else in this
                # state.
                self.localControl = (avId == base.localAvatar.doId)
                if self.localControl and self.crane and not self.crane.magnetOn:
                    self._grabConfirmedForDrop = True
                    self.demand('LocalDropped', avId, craneId)
                return
            else:
                # Whoops, we had previously grabbed it locally, but it
                # turns out someone else grabbed it instead.
                self.crane.dropObject(self)
                self.prepareRelease()
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)
        self.localControl = (avId == base.localAvatar.doId)

        # The "crane" might actually be the boss cog himself!  This
        # happens when the boss takes a safe to wear as a helmet.

        self.hideShadows()
        self.prepareGrab()
        self.crane.grabObject(self)

    def exitGrabbed(self):
        if self.crane:
            self.crane.dropObject(self)
        self.prepareRelease()
        self.showShadows()
        del self.crane

    def enterLocalDropped(self, avId, craneId):
        # As in LocalGrabbed, above, this state is entered locally
        # when we drop the safe, but we have not yet received
        # acknowledgement from the AI that we've dropped it.
        
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)
        
        if getattr(self, '_grabConfirmedForDrop', False):
            self.awaitingGrabConfirm = False
            self._grabConfirmedForDrop = False
        else:
            self.awaitingGrabConfirm = (self.oldState == 'LocalGrabbed')
        if avId == base.localAvatar.doId:
            self.localControl = True
        self.activatePhysics()
        if not self.awaitingGrabConfirm:
            self.startPosHprBroadcast()
        self.hideShadows()

        # Set slippery physics so it will slide off the boss.
        self.handler.setStaticFrictionCoef(0)
        self.handler.setDynamicFrictionCoef(0)

    def exitLocalDropped(self):
        if self.newState != 'SlidingFloor' and self.newState != 'Dropped':
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        del self.crane
        self.showShadows()

    def enterDropped(self, avId, craneId):
        # Dropped (or flung) from a player's crane, or from the boss's
        # head.  In this case, craneId is the crane we were dropped
        # from (or the boss doId).
        self.avId = avId
        self.craneId = craneId

        self.crane = self.cr.doId2do.get(craneId)

        if self.avId == base.localAvatar.doId:
            self.localControl = True
            self.activatePhysics()
            self.startPosHprBroadcast(period=.05)

            # Set slippery physics so it will slide off the boss.
            self.handler.setStaticFrictionCoef(0)
            self.handler.setDynamicFrictionCoef(0)
        else:
            self.localControl = False
            self.startSmooth()
        self.hideShadows()

    def exitDropped(self):
        if self.avId == base.localAvatar.doId:
            if self.newState != 'SlidingFloor':
                self.deactivatePhysics()
                self.stopPosHprBroadcast()
        else:
            self.stopSmooth()

        del self.crane
        self.showShadows()

    def enterSlidingFloor(self, avId):
        # The object is now sliding across the floor under local
        # control.  Crank up the friction so it will slow down more
        # quickly.
        
        self.avId = avId
        
        if self.lerpInterval:
            self.lerpInterval.finish()
            self.lerpInterval = None
            
        if self.avId == base.localAvatar.doId:
            self.localControl = True
            self.activatePhysics()
            self.startPosHprBroadcast(period=.05)
            
            self.handler.setStaticFrictionCoef(0.9)
            self.handler.setDynamicFrictionCoef(0.5)

            # Start up a task to watch for it to actually stop drifting.
            # When it does, we notify the AI.
            if self.wantsWatchDrift:
                taskMgr.add(self.__watchDrift, self.watchDriftName)
        else:
            self.localControl = False
            self.startSmooth()
            
        self.hitFloorSoundInterval.start()

    def exitSlidingFloor(self):
        if self.avId == base.localAvatar.doId:
            taskMgr.remove(self.watchDriftName)
            self.deactivatePhysics()
            self.stopPosHprBroadcast()
        else:
            self.stopSmooth()

    def enterFree(self):
        if not self.awaitingGrabConfirm:
            self.avId = 0
            self.craneId = 0
        self.localControl = False

    def exitFree(self):
        pass
