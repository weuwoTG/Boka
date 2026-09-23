"""
This module contains the class used to communicate with Telegram's servers
in plain text, when no authorization key has been created yet.
"""

import struct

from .mtprotostate import MTProtoState
from ..errors import InvalidBufferError
from ..extensions import BinaryReader


class MTProtoPlainSender:
    """
    MTProto Mobile Protocol plain sender
    (https://core.telegram.org/mtproto/description#unencrypted-messages)
    """

    def __init__(self, connection, *, loggers):
        """
        Initializes the MTProto plain sender.

        :param connection: the Connection to be used.
        """
        self._state = MTProtoState(auth_key=None, loggers=loggers)
        self._connection = connection

    async def send(self, request):
        """
        Sends and receives the result for the given request.
        """
        body = bytes(request)
        msg_id = self._state._get_new_msg_id()
        await self._connection.send(struct.pack("<qqi", 0, msg_id, len(body)) + body)

        body = await self._connection.recv()
        if len(body) < 8:
            raise InvalidBufferError(body)

        with BinaryReader(body) as reader:
            auth_key_id = reader.read_long()
            assert auth_key_id == 0, "Bad auth_key_id"

            msg_id = reader.read_long()
            assert msg_id != 0, "Bad msg_id"
                                                                       
                                                                        
                                                                         
                                                                      

            length = reader.read_int()
            assert length > 0, "Bad length"
                                                                              
                                                                            
                                                                               
            return reader.tgread_object()
