#!/usr/bin/env python

from dataclasses import dataclass, field

from kontor.defines import FileType, TransmissionType


@dataclass
class ApplicantDossier:
    username: str = ""
    password_hash: str = ""
    allowed_procedures: list = field(default_factory=list)


@dataclass
class ProcedureProtocol:
    name: str = ""
    operation: str = ""
    error_codes: list = field(default_factory=list)
    max_repeats_if_failed: int = 3
    time_seconds_between_repeats: int = 10


@dataclass
class BureauOperationProtocol:
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
    type: TransmissionType = TransmissionType.AUTH_REQUEST
    username: str = ""
    password_hash: str = ""


@dataclass
class AuthResponseMessage:
    type: TransmissionType = TransmissionType.AUTH_RESPONSE
    is_authenticated: bool = False
    message: str = ""


@dataclass
class ProcedureRequestMessage:
    type: TransmissionType = TransmissionType.PROCEDURE_REQUEST
    procedure: str = ""
    file_type: FileType = FileType.NONE
    file_name: str = ""
    file_size_bytes: int = 0
    file_crc32: str = ""


@dataclass
class ProcedureResponseMessage:
    type: TransmissionType = TransmissionType.PROCEDURE_RESPONSE
    is_ready_for_procedure: bool = False
    message: str = ""


@dataclass
class FileReceivingReceiptMessage:
    type: TransmissionType = TransmissionType.FILE_RECEIVING_RECEIPT
    is_received_correctly: bool = False
    message: str = ""


@dataclass
class ProcedureReceiptMessage:
    type: TransmissionType = TransmissionType.PROCEDURE_RECEIPT
    is_processed_correctly: bool = False
    message: str = ""
    file_size_bytes: int = 0
    file_crc32: str = ""
