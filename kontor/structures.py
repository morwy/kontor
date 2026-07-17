#!/usr/bin/env python

"""
This module defines the data structures used in the Kontor application for representing applicants, procedures, and messages exchanged between the applicant and the clerk.
"""

from dataclasses import dataclass, field

from kontor.defines import FileType, TransmissionType


@dataclass
class ApplicantDossier:
    """
    Represents the dossier of an applicant, including their credentials and allowed procedures.

    Attributes:
        username: The username of the applicant.
        password_hash: The hashed password of the applicant. Password is hashed with SHA512 and stored as a string of hexadecimal digits.
        allowed_procedures: A list of procedure names that the applicant is allowed to execute.
    """

    username: str = ""
    password_hash: str = ""
    allowed_procedures: list = field(default_factory=list)


@dataclass
class ProcedureProtocol:
    """
    Represents the protocol for a specific procedure that can be executed by the clerk.

    Attributes:
        name: The name of the procedure.
        operation: A description of the operation performed by the procedure.
        timeout_in_seconds: The maximum time in seconds that the procedure can take to complete. Default is 60 seconds.
        error_codes: A list of error codes that will cause the procedure to be considered as failed. If the procedure returns an error code that is not in this list, it will be considered as successful. Default is an empty list, meaning that any exit code will be considered a success.
        max_repeats_if_failed: The maximum number of times the clerk can repeat the procedure if it fails.
        time_seconds_between_repeats: The time in seconds that the clerk must wait between repeat attempts of the procedure after a failure.
        time_seconds_between_procedures: The time in seconds that the clerk must wait between executing this procedure and any subsequent procedure, regardless of success or failure. A value of 0 means no waiting time is required between procedures.
    """

    name: str = ""
    operation: str = ""

    timeout_in_seconds: int = 60

    error_codes: list = field(default_factory=list)

    max_repeats_if_failed: int = 3
    time_seconds_between_repeats: int = 10

    time_seconds_between_procedures: int = 0


@dataclass
class BureauOperationProtocol:
    """
    Represents the overall protocol for the bureau operation, including server settings and available procedures.

    Attributes:
        ip_address: The IP address on which the bureau server listens for incoming connections.
        port: The port number on which the bureau server listens for incoming connections.

        chunk_size_kilobytes: The size of data chunks in kilobytes used for file transmission.
        client_idle_timeout_seconds: The time in seconds after which an idle client connection is closed by the bureau.
        max_storage_period_hours: The maximum period in hours for which the bureau can store received files before they are automatically deleted. A value of 0 means no automatic deletion.
        max_parallel_connections: The maximum number of parallel client connections that the bureau can handle simultaneously.
        max_consequent_client_procedures: The maximum number of consequent procedures that a single client can execute before being disconnected by the bureau. A value of 0 means no limit.
        max_grace_shutdown_timeout_seconds: The maximum time in seconds that the bureau waits for ongoing procedures to complete during a graceful shutdown before forcefully terminating them.

        forced_ssl_usage: A boolean flag indicating whether SSL/TLS encryption is enforced for all communications between the applicant and the bureau. If set to True, all connections must use SSL/TLS; if False, SSL/TLS is optional.
        certificate_path: The file path to the SSL/TLS certificate used by the bureau for encrypted communications. This should be provided if forced_ssl_usage is True or if SSL/TLS is desired.
        certificate_key_path: The file path to the private key corresponding to the SSL/TLS certificate used by the bureau. This should be provided if forced_ssl_usage is True or if SSL/TLS is desired.

        procedures: A dictionary mapping procedure names (strings) to their corresponding ProcedureProtocol objects, representing all procedures available for execution by applicants.
    """

    ip_address: str = "localhost"
    port: int = 5690
    chunk_size_kilobytes: int = 256
    client_idle_timeout_seconds: int = 30
    max_storage_period_hours: int = 0
    max_parallel_connections: int = 100
    max_consequent_client_procedures: int = 1
    max_grace_shutdown_timeout_seconds: int = 30

    forced_ssl_usage: bool = False
    certificate_path: str = ""
    certificate_key_path: str = ""

    procedures: dict = field(default_factory=dict)


@dataclass
class AuthRequestMessage:
    """
    Represents an authentication request message sent from the applicant to the clerk.

    Attributes:
        type: The type of the transmission, set to TransmissionType.AUTH_REQUEST.
        username: The username of the applicant attempting to authenticate.
        password_hash: The hashed password of the applicant, hashed with SHA512 and represented as a string of hexadecimal digits.
    """

    type: TransmissionType = TransmissionType.AUTH_REQUEST
    username: str = ""
    password_hash: str = ""


@dataclass
class AuthResponseMessage:
    """
    Represents an authentication response message sent from the clerk to the applicant in response to an authentication request.

    Attributes:
        type: The type of the transmission, set to TransmissionType.AUTH_RESPONSE.
        is_authenticated: A boolean flag indicating whether the authentication was successful (True) or not (False).
        message: An optional message providing additional information about the authentication result, such as error details in case of failure or a welcome message in case of success.
    """

    type: TransmissionType = TransmissionType.AUTH_RESPONSE
    is_authenticated: bool = False
    message: str = ""


@dataclass
class ProcedureRequestMessage:
    """
    Represents a procedure request message sent from the applicant to the bureau.

    Attributes:
        type: The type of the transmission, set to TransmissionType.PROCEDURE_REQUEST.
        procedure: The name of the procedure to be executed.
        file_type: The type of the file being submitted for the procedure.
        file_name: The name of the file being submitted for the procedure.
    """

    type: TransmissionType = TransmissionType.PROCEDURE_REQUEST
    procedure: str = ""
    file_type: FileType = FileType.NONE
    file_name: str = ""
    file_size_bytes: int = 0
    file_crc32: str = ""


@dataclass
class ProcedureResponseMessage:
    """
    Represents a procedure response message sent from the bureau to the applicant in response to a procedure request.

    Attributes:
        type: The type of the transmission, set to TransmissionType.PROCEDURE_RESPONSE.
        is_ready_for_procedure: A boolean flag indicating whether the procedure is ready for execution (True) or not (False).
        message: An optional message providing additional information about the procedure result.
    """

    type: TransmissionType = TransmissionType.PROCEDURE_RESPONSE
    is_ready_for_procedure: bool = False
    message: str = ""


@dataclass
class FileReceivingReceiptMessage:
    """
    Represents a file receiving receipt message sent from the bureau to the applicant upon successful file reception.

    Attributes:
        type: The type of the transmission, set to TransmissionType.FILE_RECEIVING_RECEIPT.
        is_received_correctly: A boolean flag indicating whether the file was received correctly (True) or not (False).
        message: An optional message providing additional information about the file reception result.
    """

    type: TransmissionType = TransmissionType.FILE_RECEIVING_RECEIPT
    is_received_correctly: bool = False
    message: str = ""


@dataclass
class ProcedureReceiptMessage:
    """
    Represents a procedure receipt message sent from the bureau to the applicant upon successful procedure processing.

    Attributes:
        type: The type of the transmission, set to TransmissionType.PROCEDURE_RECEIPT.
        is_processed_correctly: A boolean flag indicating whether the procedure was processed correctly (True) or not (False).
        message: An optional message providing additional information about the procedure processing result.
    """

    type: TransmissionType = TransmissionType.PROCEDURE_RECEIPT
    is_processed_correctly: bool = False
    message: str = ""
    file_size_bytes: int = 0
    file_crc32: str = ""
