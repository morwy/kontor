#!/usr/bin/env python


class ServerCertificateMissingException(Exception):
    pass


class ServerCertificateKeyMissingException(Exception):
    pass


class ConnectionBrokenException(Exception):
    pass


class ConnectionTimeoutException(Exception):
    pass


class InvalidMessageFormatException(Exception):
    pass


class UnexpectedMessageException(Exception):
    pass


class AuthenticationFailureException(Exception):
    pass


class ProcedureApprovalException(Exception):
    pass


class ProcedureExecutionException(Exception):
    pass


class ProcedureAlreadyPresentException(Exception):
    pass


class FileTransmissionException(Exception):
    pass


class EmptyFileListException(Exception):
    pass


class MissingWorkingDirectoryException(Exception):
    pass


class ServerStartTimeoutException(Exception):
    pass
