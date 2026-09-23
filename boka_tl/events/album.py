import asyncio
import time
import weakref

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types
from ..tl.custom.sendergetter import SenderGetter

_IGNORE_MAX_SIZE = 100         
_IGNORE_MAX_AGE = 5           

                                                                         
                                                                         
                                                                         
_IGNORE_DICT = {}


_HACK_DELAY = 0.5


class AlbumHack:
    """
    When receiving an album from a different data-center, they will come in
    separate `Updates`, so we need to temporarily remember them for a while
    and only after produce the event.

    Of course events are not designed for this kind of wizardy, so this is
    a dirty hack that gets the job done.

    When cleaning up the code base we may want to figure out a better way
    to do this, or just leave the album problem to the users; the update
    handling code is bad enough as it is.
    """

    def __init__(self, client, event):
                                                                          
                                                                         
        self._client = weakref.ref(client)
        self._event = event                
        self._due = client.loop.time() + _HACK_DELAY

        client.loop.create_task(self.deliver_event())

    def extend(self, messages):
        client = self._client()
        if client:                       
            self._event.messages.extend(messages)
            self._due = client.loop.time() + _HACK_DELAY

    async def deliver_event(self):
        while True:
            client = self._client()
            if client is None:
                return                                       

            diff = self._due - client.loop.time()
            if diff <= 0:
                                                                         
                                                                            
                await client._dispatch_event(self._event)
                return

            del client                                          
            await asyncio.sleep(diff)


@name_inner_event
class Album(EventBuilder):
    """
    Occurs whenever you receive an album. This event only exists
    to ease dealing with an unknown amount of messages that belong
    to the same album.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.Album)
            async def handler(event):
                # Counting how many photos or videos the album has
                print('Got an album with', len(event), 'items')

                # Forwarding the album as a whole to some chat
                event.forward_to(chat)

                # Printing the caption
                print(event.text)

                # Replying to the fifth item in the album
                await event.messages[4].reply('Cool!')
    """

    def __init__(self, chats=None, *, blacklist_chats=False, func=None):
        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)

    @classmethod
    def build(cls, update, others=None, self_id=None):
                                                                               
                                                                                
                                                                                           
        others = [update]

        if isinstance(update, (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            if not isinstance(update.message, types.Message):
                return                                             

            group = update.message.grouped_id
            if group is None:
                return                      

                                                                    
                                                                   
                                                   
            if _IGNORE_DICT.pop(id(update), None):
                return

                                                                        
                                                                             
            now = time.time()
            if len(_IGNORE_DICT) > _IGNORE_MAX_SIZE:
                for i in [
                    i for i, t in _IGNORE_DICT.items() if now - t > _IGNORE_MAX_AGE
                ]:
                    del _IGNORE_DICT[i]

                                                      
            for u in others:
                if u is not update:
                    _IGNORE_DICT[id(u)] = now

                                                                         
            return cls.Event(
                [
                    u.message
                    for u in others
                    if (
                        isinstance(
                            u, (types.UpdateNewMessage, types.UpdateNewChannelMessage)
                        )
                        and isinstance(u.message, types.Message)
                        and u.message.grouped_id == group
                    )
                ]
            )

    def filter(self, event):
                                                                         
        if len(event.messages) > 1:
            return super().filter(event)

    class Event(EventCommon, SenderGetter):
        """
        Represents the event of a new album.

        Members:
            messages (Sequence[`Message <telethon.tl.custom.message.Message>`]):
                The list of messages belonging to the same album.
        """

        def __init__(self, messages):
            message = messages[0]
            super().__init__(
                chat_peer=message.peer_id,
                msg_id=message.id,
                broadcast=bool(message.post),
            )
            SenderGetter.__init__(self, message.sender_id)
            self.messages = messages

        def _set_client(self, client):
            super()._set_client(client)
            self._sender, self._input_sender = utils._get_entity_pair(
                self.sender_id, self._entities, client._mb_entity_cache
            )

            for msg in self.messages:
                msg._finish_init(client, self._entities, None)

            if len(self.messages) == 1:
                                                                    
                hack = client._albums.get(self.grouped_id)
                if hack is None:
                    client._albums[self.grouped_id] = AlbumHack(client, self)
                else:
                    hack.extend(self.messages)

        @property
        def grouped_id(self):
            """
            The shared ``grouped_id`` between all the messages.
            """
            return self.messages[0].grouped_id

        @property
        def text(self):
            """
            The message text of the first photo with a caption,
            formatted using the client's default parse mode.
            """
            return next((m.text for m in self.messages if m.text), "")

        @property
        def raw_text(self):
            """
            The raw message text of the first photo
            with a caption, ignoring any formatting.
            """
            return next((m.raw_text for m in self.messages if m.raw_text), "")

        @property
        def is_reply(self):
            """
            `True` if the album is a reply to some other message.

            Remember that you can access the ID of the message
            this one is replying to through `reply_to_msg_id`,
            and the `Message` object with `get_reply_message()`.
            """
                                                                               
            return self.messages[0].is_reply

        @property
        def forward(self):
            """
            The `Forward <telethon.tl.custom.forward.Forward>`
            information for the first message in the album if it was forwarded.
            """
                                                                               
            return self.messages[0].forward

                                     

                               

        async def get_reply_message(self):
            """
            The `Message <telethon.tl.custom.message.Message>`
            that this album is replying to, or `None`.

            The result will be cached after its first use.
            """
            return await self.messages[0].get_reply_message()

        async def respond(self, *args, **kwargs):
            """
            Responds to the album (not as a reply). Shorthand for
            `telethon.client.messages.MessageMethods.send_message`
            with ``entity`` already set.
            """
            return await self.messages[0].respond(*args, **kwargs)

        async def reply(self, *args, **kwargs):
            """
            Replies to the first photo in the album (as a reply). Shorthand
            for `telethon.client.messages.MessageMethods.send_message`
            with both ``entity`` and ``reply_to`` already set.
            """
            return await self.messages[0].reply(*args, **kwargs)

        async def forward_to(self, *args, **kwargs):
            """
            Forwards the entire album. Shorthand for
            `telethon.client.messages.MessageMethods.forward_messages`
            with both ``messages`` and ``from_peer`` already set.
            """
            if self._client:
                kwargs["messages"] = self.messages
                kwargs["from_peer"] = await self.get_input_chat()
                return await self._client.forward_messages(*args, **kwargs)

        async def edit(self, *args, **kwargs):
            """
            Edits the first caption or the message, or the first messages'
            caption if no caption is set, iff it's outgoing. Shorthand for
            `telethon.client.messages.MessageMethods.edit_message`
            with both ``entity`` and ``message`` already set.

            Returns `None` if the message was incoming,
            or the edited `Message` otherwise.

            .. note::

                This is different from `client.edit_message
                <telethon.client.messages.MessageMethods.edit_message>`
                and **will respect** the previous state of the message.
                For example, if the message didn't have a link preview,
                the edit won't add one by default, and you should force
                it by setting it to `True` if you want it.

                This is generally the most desired and convenient behaviour,
                and will work for link previews and message buttons.
            """
            for msg in self.messages:
                if msg.raw_text:
                    return await msg.edit(*args, **kwargs)

            return await self.messages[0].edit(*args, **kwargs)

        async def delete(self, *args, **kwargs):
            """
            Deletes the entire album. You're responsible for checking whether
            you have the permission to do so, or to except the error otherwise.
            Shorthand for
            `telethon.client.messages.MessageMethods.delete_messages` with
            ``entity`` and ``message_ids`` already set.
            """
            if self._client:
                return await self._client.delete_messages(
                    await self.get_input_chat(), self.messages, *args, **kwargs
                )

        async def mark_read(self):
            """
            Marks the entire album as read. Shorthand for
            `client.send_read_acknowledge()
            <telethon.client.messages.MessageMethods.send_read_acknowledge>`
            with both ``entity`` and ``message`` already set.
            """
            if self._client:
                await self._client.send_read_acknowledge(
                    await self.get_input_chat(), max_id=self.messages[-1].id
                )

        async def pin(self, *, notify=False):
            """
            Pins the first photo in the album. Shorthand for
            `telethon.client.messages.MessageMethods.pin_message`
            with both ``entity`` and ``message`` already set.
            """
            return await self.messages[0].pin(notify=notify)

        def __len__(self):
            """
            Return the amount of messages in the album.

            Equivalent to ``len(self.messages)``.
            """
            return len(self.messages)

        def __iter__(self):
            """
            Iterate over the messages in the album.

            Equivalent to ``iter(self.messages)``.
            """
            return iter(self.messages)

        def __getitem__(self, n):
            """
            Access the n'th message in the album.

            Equivalent to ``event.messages[n]``.
            """
            return self.messages[n]
