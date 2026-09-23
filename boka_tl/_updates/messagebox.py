"""
This module deals with correct handling of updates, including gaps, and knowing when the code
should "get difference" (the set of updates that the client should know by now minus the set
of updates that it actually knows).

Each chat has its own [`Entry`] in the [`MessageBox`] (this `struct` is the "entry point").
At any given time, the message box may be either getting difference for them (entry is in
[`MessageBox::getting_diff_for`]) or not. If not getting difference, a possible gap may be
found for the updates (entry is in [`MessageBox::possible_gaps`]). Otherwise, the entry is
on its happy path.

Gaps are cleared when they are either resolved on their own (by waiting for a short time)
or because we got the difference for the corresponding entry.

While there are entries for which their difference must be fetched,
[`MessageBox::check_deadlines`] will always return [`Instant::now`], since "now" is the time
to get the difference.
"""

import asyncio
import datetime
import time
import logging
from enum import Enum
from .session import SessionState, ChannelState
from ..tl import types as tl, functions as fn
from ..helpers import get_running_loop

                                                                                       
NO_SEQ = 0

                                                                    
BOT_CHANNEL_DIFF_LIMIT = 100000
USER_CHANNEL_DIFF_LIMIT = 100

                                              
POSSIBLE_GAP_TIMEOUT = 0.5

                                                           
 
                                                                                                
                                                                                           
                                                                  
 
                                                                                              
NO_UPDATES_TIMEOUT = 15 * 60


                                                    
class Sentinel:
    __slots__ = ("tag",)

    def __init__(self, tag=None):
        self.tag = tag or "_"

    def __repr__(self):
        return self.tag


               
                                                                                       
ENTRY_ACCOUNT = Sentinel("ACCOUNT")
                                                             
ENTRY_SECRET = Sentinel("SECRET")
                                                                                                           

                                                                                       
                                                                        
LOG_LEVEL_TRACE = (logging.DEBUG - logging.NOTSET) // 2

_sentinel = Sentinel()


def next_updates_deadline():
    return get_running_loop().time() + NO_UPDATES_TIMEOUT


def epoch():
    return datetime.datetime(*time.gmtime(0)[:6]).replace(tzinfo=datetime.timezone.utc)


class GapError(ValueError):
    def __repr__(self):
        return "GapError()"


class PrematureEndReason(Enum):
    TEMPORARY_SERVER_ISSUES = "tmp"
    BANNED = "ban"


                                                                                       
class PtsInfo:
    __slots__ = ("pts", "pts_count", "entry")

    def __init__(self, pts: int, pts_count: int, entry: object):
        self.pts = pts
        self.pts_count = pts_count
        self.entry = entry

    @classmethod
    def from_update(cls, update):
        pts = getattr(update, "pts", None)
        if pts:
            pts_count = getattr(update, "pts_count", None) or 0
            try:
                entry = update.message.peer_id.channel_id
            except AttributeError:
                entry = getattr(update, "channel_id", None) or ENTRY_ACCOUNT
            return cls(pts=pts, pts_count=pts_count, entry=entry)

        qts = getattr(update, "qts", None)
        if qts:
            return cls(pts=qts, pts_count=1, entry=ENTRY_SECRET)

        return None

    def __repr__(self):
        return (
            f"PtsInfo(pts={self.pts}, pts_count={self.pts_count}, entry={self.entry})"
        )


                                                     
class State:
    __slots__ = ("pts", "deadline")

    def __init__(
        self,
                                             
        pts: int,
                                                                                                 
        deadline: float,
    ):
        self.pts = pts
        self.deadline = deadline

    def __repr__(self):
        return f"State(pts={self.pts}, deadline={self.deadline})"


                       
                                                                                
                                                                                  
                                                                                                          
                                  
 
                                                                                                               
                                                                                                              
class PossibleGap:
    __slots__ = ("deadline", "updates")

    def __init__(
        self,
        deadline: float,
                                                                                                 
        updates: list,              
    ):
        self.deadline = deadline
        self.updates = updates

    def __repr__(self):
        return (
            f"PossibleGap(deadline={self.deadline}, update_count={len(self.updates)})"
        )


                                                                
 
                                                                            
class MessageBox:
    __slots__ = (
        "_log",
        "map",
        "date",
        "seq",
        "next_deadline",
        "possible_gaps",
        "getting_diff_for",
    )

    def __init__(
        self,
        log,
                                                
        map: dict = _sentinel,                  
                                                                 
        date: datetime.datetime = epoch() + datetime.timedelta(seconds=1),
        seq: int = NO_SEQ,
                                                                                                               
        next_deadline: object = None,         
                                                                                 
         
                                                                                                                   
                                                                 
         
                                                                                                                       
                         
        possible_gaps: dict = _sentinel,                        
                                                                
        getting_diff_for: set = _sentinel,         
    ):
        self._log = log
        self.map = {} if map is _sentinel else map
        self.date = date
        self.seq = seq
        self.next_deadline = next_deadline
        self.possible_gaps = {} if possible_gaps is _sentinel else possible_gaps
        self.getting_diff_for = (
            set() if getting_diff_for is _sentinel else getting_diff_for
        )

        if __debug__:
            self._trace("MessageBox initialized")

    def _trace(self, msg, *args, **kwargs):
                                                                                    
                                                                                    
                                                                                 
                                                         
        self._log.log(
            LOG_LEVEL_TRACE,
            "Current MessageBox state: seq = %r, date = %s, map = %r",
            self.seq,
            self.date.isoformat(),
            self.map,
        )
        self._log.log(LOG_LEVEL_TRACE, msg, *args, **kwargs)

                                                        

    def load(self, session_state, channel_states):
        """
        Create a [`MessageBox`] from a previously known update state.
        """
        if __debug__:
            self._trace(
                "Loading MessageBox with session_state = %r, channel_states = %r",
                session_state,
                channel_states,
            )

        deadline = next_updates_deadline()

        self.map.clear()
        if session_state.pts != NO_SEQ:
            self.map[ENTRY_ACCOUNT] = State(pts=session_state.pts, deadline=deadline)
        if session_state.qts != NO_SEQ:
            self.map[ENTRY_SECRET] = State(pts=session_state.qts, deadline=deadline)
        self.map.update(
            (s.channel_id, State(pts=s.pts, deadline=deadline)) for s in channel_states
        )

        self.date = datetime.datetime.fromtimestamp(
            session_state.date, tz=datetime.timezone.utc
        )
        self.seq = session_state.seq
        self.next_deadline = ENTRY_ACCOUNT

    def session_state(self):
        """
        Return the current state.

        This should be used for persisting the state.
        """
        return dict(
            pts=self.map[ENTRY_ACCOUNT].pts if ENTRY_ACCOUNT in self.map else NO_SEQ,
            qts=self.map[ENTRY_SECRET].pts if ENTRY_SECRET in self.map else NO_SEQ,
            date=self.date,
            seq=self.seq,
        ), {id: state.pts for id, state in self.map.items() if isinstance(id, int)}

    def is_empty(self) -> bool:
        """
        Return true if the message box is empty and has no state yet.
        """
        return ENTRY_ACCOUNT not in self.map

    def check_deadlines(self):
        """
        Return the next deadline when receiving updates should timeout.

        If a deadline expired, the corresponding entries will be marked as needing to get its difference.
        While there are entries pending of getting their difference, this method returns the current instant.
        """
        now = get_running_loop().time()

        if self.getting_diff_for:
            return now

        deadline = next_updates_deadline()

                                                                                                   
        if self.possible_gaps:
            deadline = min(
                deadline, *(gap.deadline for gap in self.possible_gaps.values())
            )
        elif self.next_deadline in self.map:
            deadline = min(deadline, self.map[self.next_deadline].deadline)

                                                                                                      
                                                                                                       
                                                                                                           
        if now >= deadline:
                                                                                               
            self.getting_diff_for.update(
                entry
                for entry, gap in self.possible_gaps.items()
                if now >= gap.deadline
            )
            self.getting_diff_for.update(
                entry for entry, state in self.map.items() if now >= state.deadline
            )

            if __debug__:
                self._trace(
                    "Deadlines met, now getting diff for %r", self.getting_diff_for
                )

                                                                                               
                                                                                              
            for entry in self.getting_diff_for:
                self.possible_gaps.pop(entry, None)

        return deadline

                                                                               
     
                                                                                 
    def reset_deadlines(self, entries, deadline):
        if not entries:
            return
        for entry in entries:
            if entry not in self.map:
                raise RuntimeError(
                    "Called reset_deadline on an entry for which we do not have state"
                )
            self.map[entry].deadline = deadline

        if self.next_deadline in entries:
                                                                                       
            self.next_deadline = min(
                self.map.items(), key=lambda entry_state: entry_state[1].deadline
            )[0]
        elif (
            self.next_deadline in self.map
            and deadline < self.map[self.next_deadline].deadline
        ):
                                                                                                                    
                                                                            
            self.next_deadline = entry
                                                                                       

                                                                       
    def reset_channel_deadline(self, channel_id, timeout):
        self.reset_deadlines(
            {channel_id}, get_running_loop().time() + (timeout or NO_UPDATES_TIMEOUT)
        )

                            
     
                                                                                               
                              
    def set_state(self, state, reset=True):
        if __debug__:
            self._trace("Setting state %s", state)

        deadline = next_updates_deadline()

        if state.pts != NO_SEQ or not reset:
            self.map[ENTRY_ACCOUNT] = State(pts=state.pts, deadline=deadline)
        else:
            self.map.pop(ENTRY_ACCOUNT, None)

                                                                                          
                                                                        
         
                                                                        
                                                  
                                                                            
                                                                          
        if state.qts != NO_SEQ or not reset:
            self.map[ENTRY_SECRET] = State(pts=state.qts, deadline=deadline)
        else:
            self.map.pop(ENTRY_SECRET, None)

        self.date = state.date
        self.seq = state.seq

                                                                                    
     
                                                                             
    def try_set_channel_state(self, id, pts):
        if __debug__:
            self._trace("Trying to set channel state for %r: %r", id, pts)

        if id not in self.map:
            self.map[id] = State(pts=pts, deadline=next_updates_deadline())

                                                          
                                                                                                       
     
                               
    def try_begin_get_diff(self, entry, reason):
        if entry not in self.map:
                                                                                                               
            if entry in self.possible_gaps:
                raise RuntimeError(
                    "Should not have a possible_gap for an entry not in the state map"
                )

            if __debug__:
                self._trace(
                    "Should get difference for %r because %s but cannot due to missing hash",
                    entry,
                    reason,
                )
            return

        if __debug__:
            self._trace("Marking %r as needing difference because %s", entry, reason)
        self.getting_diff_for.add(entry)
        self.possible_gaps.pop(entry, None)

                                                    
     
                                  
    def end_get_diff(self, entry):
        try:
            self.getting_diff_for.remove(entry)
        except KeyError:
            raise RuntimeError(
                "Called end_get_diff on an entry which was not getting diff for"
            )

        self.reset_deadlines({entry}, next_updates_deadline())
        assert (
            entry not in self.possible_gaps
        ), "gaps shouldn't be created while getting difference"

                                                           

                                                                      

                                                               
     
                                                                                            
                                                                       
     
                                                                                
                                                                                  
                                  
     
                                                                                            
     
                                                                   
    def process_updates(
        self,
        updates,
        chat_hashes,
        result,                                                                    
    ):

                                                                                  
                                                                        
                                              
        self_outgoing = getattr(updates, "_self_outgoing", False)
        real_result = result
        result = []

        date = getattr(updates, "date", None)
        seq = getattr(updates, "seq", None)
        seq_start = getattr(updates, "seq_start", None)
        users = getattr(updates, "users", None) or []
        chats = getattr(updates, "chats", None) or []

        if __debug__:
            self._trace(
                "Processing updates with seq = %r, seq_start = %r, date = %s: %s",
                seq,
                seq_start,
                date.isoformat() if date else None,
                updates,
            )

        if date is None:
                                                                                
            self.try_begin_get_diff(ENTRY_ACCOUNT, "received updatesTooLong")
            raise GapError
        if seq is None:
            seq = NO_SEQ
        if seq_start is None:
            seq_start = seq

                                                                                                             
        updates = getattr(updates, "updates", None) or [
            updates.update if isinstance(updates, tl.UpdateShort) else updates
        ]

        for u in updates:
            u._self_outgoing = self_outgoing

                                                                                              
                                                                    
        if seq_start != NO_SEQ:
            if self.seq + 1 > seq_start:
                                                            
                if __debug__:
                    self._trace(
                        "Skipping updates as they should have already been handled"
                    )
                return (users, chats)
            elif self.seq + 1 < seq_start:
                              
                self.try_begin_get_diff(ENTRY_ACCOUNT, "detected gap")
                raise GapError
                        

        def _sort_gaps(update):
            pts = PtsInfo.from_update(update)
            return pts.pts - pts.pts_count if pts else 0

        reset_deadlines = set()                    

        result.extend(
            filter(
                None,
                (
                    self.apply_pts_info(u, reset_deadlines=reset_deadlines)
                                                                                         
                                                                                          
                                                                   
                    for u in sorted(updates, key=_sort_gaps)
                ),
            )
        )

        self.reset_deadlines(reset_deadlines, next_updates_deadline())

        if self.possible_gaps:
            if __debug__:
                self._trace(
                    "Trying to re-apply %r possible gaps", len(self.possible_gaps)
                )

                                                                                         
            for key in list(self.possible_gaps.keys()):
                self.possible_gaps[key].updates.sort(key=_sort_gaps)

                for _ in range(len(self.possible_gaps[key].updates)):
                    update = self.possible_gaps[key].updates.pop(0)

                                                                                 
                                                                                                
                    update = self.apply_pts_info(update, reset_deadlines=None)
                    if update:
                        result.append(update)
                        if __debug__:
                            self._trace(
                                "Resolved gap with %r: %s",
                                PtsInfo.from_update(update),
                                update,
                            )

                                   
            self.possible_gaps = {
                entry: gap for entry, gap in self.possible_gaps.items() if gap.updates
            }

        real_result.extend(u for u in result if not u._self_outgoing)

        if result and not self.possible_gaps:
                                                                                  
                                                                           
            if __debug__:
                self._trace("Updating seq as all updates were applied")
            if date != epoch():
                self.date = date
            if seq != NO_SEQ:
                self.seq = seq

        return (users, chats)

                                                                                 
     
                                                                                        
                                                                                     
                                         
    def apply_pts_info(
        self,
        update,
        *,
        reset_deadlines,
    ):
                                                                                                    
        if isinstance(update, tl.UpdateChannelTooLong):
            self.try_begin_get_diff(update.channel_id, "received updateChannelTooLong")
            return None

        pts = PtsInfo.from_update(update)
        if not pts:
                                                                       
            if __debug__:
                self._trace(
                    "No pts in update, so it can be applied in any order: %s", update
                )
            return update

                                                                                          
                                                          
         
                                                                                                  
         
                                                                                                           
        if reset_deadlines:
            reset_deadlines.add(pts.entry)

        if pts.entry in self.getting_diff_for:
                                                                                                 
                                               
            if __debug__:
                self._trace(
                    "Skipping update with %r as its difference is being fetched", pts
                )
            return None

        if pts.entry in self.map:
            local_pts = self.map[pts.entry].pts
            if local_pts + pts.pts_count > pts.pts:
                        
                if __debug__:
                    self._trace(
                        "Skipping update since local pts %r > %r: %s",
                        local_pts,
                        pts,
                        update,
                    )
                return None
            elif local_pts + pts.pts_count < pts.pts:
                              
                                       
                if __debug__:
                    self._trace(
                        "Possible gap since local pts %r < %r: %s",
                        local_pts,
                        pts,
                        update,
                    )
                if pts.entry not in self.possible_gaps:
                    self.possible_gaps[pts.entry] = PossibleGap(
                        deadline=get_running_loop().time() + POSSIBLE_GAP_TIMEOUT,
                        updates=[],
                    )

                self.possible_gaps[pts.entry].updates.append(update)
                return None
            else:
                       
                if __debug__:
                    self._trace(
                        "Applying update pts since local pts %r = %r: %s",
                        local_pts,
                        pts,
                        update,
                    )

                                                   
                                                     
                                                      
         
                                                                                                
                                                                                              
                                                                                             
                                                       
         
                                                                                               
                                                                                             
                                                                                               
                                                                                                  
                                                                                                
        if pts.entry in self.map:
            self.map[pts.entry].pts = pts.pts
        else:
                                                                                                  
                                                                                                          
                                                                                                 
                                                                                                              
                                                                                                          
                                                                                             
            self.map[pts.entry] = State(
                pts=(pts.pts - (0 if pts.pts_count else 1)) or 1,
                deadline=next_updates_deadline(),
            )

        return update

                                                                         

                                                     

                                                                             
    def get_difference(self):
        for entry in (ENTRY_ACCOUNT, ENTRY_SECRET):
            if entry in self.getting_diff_for:
                if entry not in self.map:
                    raise RuntimeError(
                        "Should not try to get difference for an entry without known state"
                    )

                gd = fn.updates.GetDifferenceRequest(
                    pts=self.map[ENTRY_ACCOUNT].pts,
                    pts_total_limit=None,
                    date=self.date,
                    qts=(
                        self.map[ENTRY_SECRET].pts
                        if ENTRY_SECRET in self.map
                        else NO_SEQ
                    ),
                )
                if __debug__:
                    self._trace("Requesting account difference %s", gd)
                return gd

        return None

                                                                                               
    def apply_difference(
        self,
        diff,
        chat_hashes,
    ):
        if __debug__:
            self._trace("Applying account difference %s", diff)

        finish = None
        result = None

        if isinstance(diff, tl.updates.DifferenceEmpty):
            finish = True
            self.date = diff.date
            self.seq = diff.seq
            result = [], [], []
        elif isinstance(diff, tl.updates.Difference):
            finish = True
            chat_hashes.extend(diff.users, diff.chats)
            result = self.apply_difference_type(diff, chat_hashes)
        elif isinstance(diff, tl.updates.DifferenceSlice):
            finish = False
            chat_hashes.extend(diff.users, diff.chats)
            result = self.apply_difference_type(diff, chat_hashes)
        elif isinstance(diff, tl.updates.DifferenceTooLong):
            finish = True
            self.map[ENTRY_ACCOUNT].pts = (
                diff.pts
            )                                                 
            result = [], [], []

        if finish:
            account = ENTRY_ACCOUNT in self.getting_diff_for
            secret = ENTRY_SECRET in self.getting_diff_for

            if not account and not secret:
                raise RuntimeError(
                    "Should not be applying the difference when neither account or secret was diff was active"
                )

                                                                  
            if account:
                self.end_get_diff(ENTRY_ACCOUNT)
            if secret:
                self.end_get_diff(ENTRY_SECRET)

        return result

    def apply_difference_type(
        self,
        diff,
        chat_hashes,
    ):
        state = getattr(diff, "intermediate_state", None) or diff.state
        self.set_state(state, reset=False)

                                                                                                      
                                                                                                         
        updates = []
        self.process_updates(
            tl.Updates(
                updates=diff.other_updates,
                users=diff.users,
                chats=diff.chats,
                date=epoch(),
                seq=NO_SEQ,                             
            ),
            chat_hashes,
            updates,
        )

        updates.extend(
            tl.UpdateNewMessage(
                message=m,
                pts=NO_SEQ,
                pts_count=NO_SEQ,
            )
            for m in diff.new_messages
        )
        updates.extend(
            tl.UpdateNewEncryptedMessage(
                message=m,
                qts=NO_SEQ,
            )
            for m in diff.new_encrypted_messages
        )

        return updates, diff.users, diff.chats

    def end_difference(self):
        if __debug__:
            self._trace("Ending account difference")

        account = ENTRY_ACCOUNT in self.getting_diff_for
        secret = ENTRY_SECRET in self.getting_diff_for

        if not account and not secret:
            raise RuntimeError(
                "Should not be ending get difference when neither account or secret was diff was active"
            )

                                                              
        if account:
            self.end_get_diff(ENTRY_ACCOUNT)
        if secret:
            self.end_get_diff(ENTRY_SECRET)

                                                        

                                                     

                                                                                     
    def get_channel_difference(
        self,
        chat_hashes,
    ):
        entry = next((id for id in self.getting_diff_for if isinstance(id, int)), None)
        if not entry:
            return None

        packed = chat_hashes.get(entry)
        if not packed:
                                                                     
                                              
            self.end_get_diff(entry)
                                                                                              
                                                                          
            self.map.pop(entry, None)
            return None

        state = self.map.get(entry)
        if not state:
            raise RuntimeError(
                "Should not try to get difference for an entry without known state"
            )

        gd = fn.updates.GetChannelDifferenceRequest(
            force=False,
            channel=tl.InputChannel(packed.id, packed.hash),
            filter=tl.ChannelMessagesFilterEmpty(),
            pts=state.pts,
            limit=(
                BOT_CHANNEL_DIFF_LIMIT
                if chat_hashes.self_bot
                else USER_CHANNEL_DIFF_LIMIT
            ),
        )
        if __debug__:
            self._trace("Requesting channel difference %s", gd)
        return gd

                                                                                               
    def apply_channel_difference(
        self,
        request,
        diff,
        chat_hashes,
    ):
        entry = request.channel.channel_id
        if __debug__:
            self._trace("Applying channel difference for %r: %s", entry, diff)

        self.possible_gaps.pop(entry, None)

        if isinstance(diff, tl.updates.ChannelDifferenceEmpty):
            assert diff.final
            self.end_get_diff(entry)
            self.map[entry].pts = diff.pts
            return [], [], []
        elif isinstance(diff, tl.updates.ChannelDifferenceTooLong):
            assert diff.final
            self.map[entry].pts = diff.dialog.pts
            chat_hashes.extend(diff.users, diff.chats)
            self.reset_channel_deadline(entry, diff.timeout)
                                                                                         
                                                                                       
                                                                             
            return [], [], []
        elif isinstance(diff, tl.updates.ChannelDifference):
            if diff.final:
                self.end_get_diff(entry)

            self.map[entry].pts = diff.pts
            chat_hashes.extend(diff.users, diff.chats)

            updates = []
            self.process_updates(
                tl.Updates(
                    updates=diff.other_updates,
                    users=diff.users,
                    chats=diff.chats,
                    date=epoch(),
                    seq=NO_SEQ,                             
                ),
                chat_hashes,
                updates,
            )

            updates.extend(
                tl.UpdateNewChannelMessage(
                    message=m,
                    pts=NO_SEQ,
                    pts_count=NO_SEQ,
                )
                for m in diff.new_messages
            )
            self.reset_channel_deadline(entry, None)

            return updates, diff.users, diff.chats

    def end_channel_difference(self, request, reason: PrematureEndReason, chat_hashes):
        entry = request.channel.channel_id
        if __debug__:
            self._trace("Ending channel difference for %r because %s", entry, reason)

        if reason == PrematureEndReason.TEMPORARY_SERVER_ISSUES:
                                                                                                      
            self.possible_gaps.pop(entry, None)
            self.end_get_diff(entry)
        elif reason == PrematureEndReason.BANNED:
                                                                                                   
            self.possible_gaps.pop(entry, None)
            self.end_get_diff(entry)
            del self.map[entry]
        else:
            raise RuntimeError("Unknown reason to end channel difference")

                                                        
