from abc import ABCMeta
import logging
from concurrent import futures

import grpc
import os
from django.utils.module_loading import import_string


logger = logging.getLogger(__name__)


def create_server(max_workers, port, interceptors=None):
    from django.conf import settings
    config = getattr(settings, 'GRPCSERVER', dict())
    servicers_list = config.get('servicers', [])  # callbacks to add servicers to the server
    interceptors = load_interceptors(config.get('interceptors', []))
    maximum_concurrent_rpcs = config.get('maximum_concurrent_rpcs', None)

    # create a gRPC server
    server = grpc.server(
        thread_pool=futures.ThreadPoolExecutor(max_workers=max_workers),
        # interceptors=interceptors,
        maximum_concurrent_rpcs=maximum_concurrent_rpcs
    )

    add_servicers(server, servicers_list)
    server.add_insecure_port('[::]:%s' % port)
    return server

def create_secure_server(max_workers, port, interceptors=None):
    from django.conf import settings
    config = getattr(settings, 'GRPCSERVER', dict())
    servicers_list = config.get('servicers', [])  # callbacks to add servicers to the server
    interceptors = load_interceptors(config.get('interceptors', []))
    maximum_concurrent_rpcs = config.get('maximum_concurrent_rpcs', None)
    # ##########################
    from config.settings.settings import CRT_DIR, KEY_DIR
    with open(KEY_DIR, 'rb') as f:
        private_key = f.read()
    with open(CRT_DIR, 'rb') as f:
        certificate_chain = f.read()

    server_credentials = grpc.ssl_server_credentials(
      ((private_key, certificate_chain,),))

    # create a gRPC server
    server = grpc.server(
        thread_pool=futures.ThreadPoolExecutor(max_workers=max_workers),
        # interceptors=interceptors,
        maximum_concurrent_rpcs=maximum_concurrent_rpcs
    )

    add_servicers(server, servicers_list)
    server.add_secure_port('[::]:%s' % port, server_credentials)
    return server


def add_servicers(server, servicers_list):
    """
    Add servicers to the server
    """
    if len(servicers_list) == 0:
        logger.warning("No servicers configured. Did you add GRPSERVER['servicers'] list to settings?")

    for path in servicers_list:
        logger.debug("Adding servicers from %s", path)
        callback = import_string(path)
        callback(server)


def load_interceptors(strings):
    if not strings:
        return None
    result = []
    for path in strings:
        logger.debug("Initializing interceptor from %s", path)
        result.append(import_string(path)())
    return result

def extract_handlers(server):
    for path, it in server._state.generic_handlers[0]._method_handlers.items():
        unary = it.unary_unary
        if unary is None:
            name = "???"
            params = "???"
            abstract = 'DOES NOT EXIST'
        else:
            code = it.unary_unary.__code__
            name = code.co_name
            params = ", ".join(code.co_varnames)
            abstract = ''
            if isinstance(it.__class__, ABCMeta):
                abstract = 'NOT IMPLEMENTED'

        yield "{path}: {name}({params}) {abstract}".format(
            path=path,
            name=name,
            params=params,
            abstract=abstract
        )

# def create_client(target):
#     from config.settings.settings import CRT_DIR
#     print("HERE, CRT_DIR: ", CRT_DIR)
#     if CRT_DIR is not None:
#         try:
#             with open(CRT_DIR, 'rb') as f:
#                 f.seek(0) #ensure you're at the start of the file..
#                 first_char = f.read(1) #get the first character
#                 if not first_char:
#                     # empty cert, create insecure client
#                     print("empty cert, create insecure client")
#                     return grpc.insecure_channel(target)
#                 else:
#                     f.seek(0)
#                     trusted_certs = f.read()
#                     print("TRUSTED CERT: ", trusted_certs)
#                     # grpc.ssl_channel_credentials(root_certificates=None, private_key=None, certificate_chain=None)
#                     credentials = grpc.ssl_channel_credentials(root_certificates=trusted_certs)
#                     # grpc.secure_channel(target, credentials, options=None, compression=None)
#                     return grpc.secure_channel(target, credentials)
#         except IOError: 
#             # no cert file, create insecure client
#             print("no cert file, create insecure client")
#             return grpc.insecure_channel(target)
#     else:
#         # no cert dir, create insecure client
#         print("no cert dir, create insecure client")
#         return grpc.insecure_channel(target)


def create_client(target):
    from config.settings.settings import CRT_DIR
    if CRT_DIR is not None:
        try:
            with open(CRT_DIR, 'rb') as f:
                trusted_certs = f.read()
                credentials = grpc.ssl_channel_credentials(root_certificates=trusted_certs)
                return grpc.secure_channel(target, credentials)
        except IOError: 
            # no cert file, create insecure client
            print("cert file not found, create insecure client")
            return grpc.insecure_channel(target)
    else:
        # no cert dir, create insecure client
        print("cert dir not found, create insecure client")
        return grpc.insecure_channel(target)