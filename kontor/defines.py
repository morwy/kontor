#!/usr/bin/env python

"""
This module defines the constants and enumerations used in the Kontor application.
"""

from enum import Enum

# Markers for transmission boundaries
MARKER_TRANSMISSION_START: str = "<TRANSMISSION_START>"
MARKER_TRANSMISSION_END: str = "<TRANSMISSION_END>"

# Markers for file boundaries
MARKER_FILE_START: bytes = b"<FILE_START>"
MARKER_FILE_END: bytes = b"<FILE_END>"


class TransmissionType(str, Enum):
    """
    Defines the types of messages that can be transmitted between the applicant and the clerk.
    Values are sorted in the order of expected occurrence during a typical procedure execution.

    Attributes:
        UNKNOWN: Unknown or uninitialized transmission type.
        CLERK_READY: Clerk is ready to receive requests.
        APPLICANT_READY: Applicant is ready to send requests.
        AUTH_REQUEST: Authentication request from applicant to clerk.
        AUTH_RESPONSE: Response from clerk to applicant regarding authentication.
        PROCEDURE_REQUEST: Request from applicant to clerk to execute a procedure.
        PROCEDURE_RESPONSE: Response from clerk to applicant regarding the procedure execution.
        FILE_RECEIVING_RECEIPT: Receipt from the clerk to the applicant confirming the receipt of a file.
        PROCEDURE_RECEIPT: Receipt from the clerk to the applicant confirming the processing of a procedure, including the file size and CRC32 checksum if applicable.
    """

    UNKNOWN = "UNKNOWN"
    CLERK_READY = "CLERK_READY"
    APPLICANT_READY = "APPLICANT_READY"
    AUTH_REQUEST = "AUTH_REQUEST"
    AUTH_RESPONSE = "AUTH_RESPONSE"
    PROCEDURE_REQUEST = "PROCEDURE_REQUEST"
    PROCEDURE_RESPONSE = "PROCEDURE_RESPONSE"
    FILE_RECEIVING_RECEIPT = "FILE_RECEIVING_RECEIPT"
    PROCEDURE_RECEIPT = "PROCEDURE_RECEIPT"


class FileType(str, Enum):
    """
    Defines the types of files that can be transmitted.

    Attributes:
        NONE: No file is being transmitted.
        SINGLE: A single file is being transmitted.
        ARCHIVE: An archive (e.g., ZIP) containing multiple files is being transmitted.
    """

    NONE = "NONE"
    SINGLE = "SINGLE"
    ARCHIVE = "ARCHIVE"
