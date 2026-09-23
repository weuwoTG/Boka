"""
This module holds all the base and automatically generated errors that the
Telegram API has. See telethon_generator/errors.json for more.
"""

import re

from .common import (
    ReadCancelledError,
    TypeNotFoundError,
    InvalidChecksumError,
    InvalidBufferError,
    AuthKeyNotFound,
    SecurityError,
    CdnFileTamperedError,
    AlreadyInConversationError,
    BadMessageError,
    MultiError,
    ImageProcessFailedError,
)

                                                             
from .rpcbaseerrors import *
from .rpcerrorlist import *


def rpc_message_to_error(rpc_error, request):
    """
    Converts a Telegram's RPC Error to a Python error.

    :param rpc_error: the RpcError instance.
    :param request: the request that caused this error.
    :return: the RPCError as a Python exception that represents this error.
    """
                                                             
                                                                      
    cls = rpc_errors_dict.get(rpc_error.error_message.upper(), None)
    if cls:
        return cls(request=request)

    for msg_regex, cls in rpc_errors_re:
        m = re.match(msg_regex, rpc_error.error_message)
        if m:
            capture = int(m.group(1)) if m.groups() else None
            return cls(request=request, capture=capture)

                               
                                      
                          
     
                                                                     
                              
    cls = base_errors.get(abs(rpc_error.error_code), RPCError)
    return cls(
        request=request, message=rpc_error.error_message, code=rpc_error.error_code
    )
