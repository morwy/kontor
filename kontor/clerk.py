#!/usr/bin/env python

import binascii
import dataclasses
import datetime
import glob
import json
import logging
import os
import pathlib
import platform
import shutil
import socket
import ssl
import subprocess
import time
import zipfile
from enum import Enum

from dacite import Config, from_dict

from kontor.defines import FileType, TransmissionType
from kontor.exceptions import (
    AuthenticationFailureException,
    ConnectionBrokenException,
    InvalidMessageFormatException,
    ProcedureApprovalException,
    ProcedureExecutionException,
    UnexpectedMessageException,
)
from kontor.functions import (
    send_file,
    send_message,
    wait_and_receive_file,
    wait_and_receive_message,
)
from kontor.structures import (
    AuthRequestMessage,
    AuthResponseMessage,
    BureauOperationProtocol,
    FileReceivingReceiptMessage,
    ProcedureProtocol,
    ProcedureReceiptMessage,
    ProcedureRequestMessage,
    ProcedureResponseMessage,
)


class Clerk:
    def __init__(
        self,
        bureau_operation_protocol: BureauOperationProtocol,
        temp_directory: str,
        applicant,
        address,
        is_user_auth_correct_callback,
        is_procedure_allowed_for_user_callback,
    ):
        self.__configuration = bureau_operation_protocol
        self.__temp_directory = temp_directory

        self.__applicant = applicant
        self.__address = address
        self.__is_bureau_shutting_down = False

        self.__is_user_auth_correct_callback = is_user_auth_correct_callback
        self.__is_procedure_allowed_for_user_callback = (
            is_procedure_allowed_for_user_callback
        )

        if isinstance(self.__applicant, ssl.SSLSocket):
            logging.debug(
                "%s: Clerk is communicating with Applicant via SSL connection.", address
            )
        elif isinstance(self.__applicant, socket.socket):
            logging.debug(
                "%s: Clerk is communicating with Applicant via non-SSL connection.",
                address,
            )

    def __is_file_accessible1(self, address, file_path: str) -> bool:
        try:
            if not os.access(file_path, os.R_OK):
                return False

            if not os.access(file_path, os.W_OK):
                return False

            return True

        except Exception as exception:
            logging.exception(
                "%s: Caught exception during file access checkup (%s).",
                address,
                str(exception),
            )
            return False

    def __is_file_accessible2(self, address, file_path: str) -> bool:
        try:
            if platform.system() == "Windows":
                os.rename(file_path, file_path)

            with open(file_path, "rb") as _:
                pass

            with open(file_path, "wb") as _:
                pass

            return True

        except Exception as exception:
            logging.exception(
                "%s: Caught exception during file access checkup (%s).",
                address,
                str(exception),
            )
            return False

    def __wait_until_file_is_accessible(self, address, file_path: str):
        logging.debug("Checking accessibility of file '%s'", file_path)

        max_retries = 12
        for current_retry in range(max_retries):
            is_file_accessible1 = self.__is_file_accessible1(address, file_path)
            if is_file_accessible1:
                logging.debug(
                    "File '%s' was reported as accessible by os.access().", file_path
                )
            else:
                logging.debug(
                    "File '%s' was reported as inaccessible by os.access().",
                    file_path,
                )

            # is_file_accessible2 = self.__is_file_accessible2(address, file_path)
            # if is_file_accessible2:
            #     logging.debug(
            #         "File '%s' was reported as accessible by open() and os.rename() functions.",
            #         file_path,
            #     )
            # else:
            #     logging.debug(
            #         "File '%s' was reported as inaccessible by open() and os.rename() functions.",
            #         file_path,
            #     )

            if is_file_accessible1:
                return

            logging.info(
                "%s: Waiting until file will be accessible for procedure (%d out of %d retries).",
                address,
                current_retry,
                max_retries,
            )
            time.sleep(5)

    def notify_about_shutdown(self):
        logging.info("%s: Clerk was notified about shutdown.", self.__address)
        self.__is_bureau_shutting_down = True

    def provide_service(self):
        logging.info("%s: Starting new thread for connection.", self.__address)

        try:
            username = ""
            procedure = ""
            user_temp_folder_path = ""
            is_authenticated = False

            is_connection_alive = True
            while not self.__is_bureau_shutting_down and is_connection_alive:
                message_json = wait_and_receive_message(
                    self.__applicant, self.__address
                )

                if "type" not in message_json:
                    logging.error(
                        "%s: No 'type' stated in the incoming message, terminating connection.",
                        self.__address,
                    )
                    raise InvalidMessageFormatException(
                        f"{self.__address}: No 'type' stated in the incoming message, terminating connection."
                    )

                if message_json["type"] == TransmissionType.AUTH_REQUEST:
                    if is_authenticated:
                        auth_response = AuthResponseMessage(
                            is_authenticated=False, message="Unexpected message type."
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(auth_response),
                        )
                        logging.error(
                            "%s: User is trying to re-authenticate while already being authenticated, terminating connection.",
                            self.__address,
                        )
                        raise UnexpectedMessageException(
                            f"{self.__address}: User is trying to re-authenticate while already being authenticated, terminating connection."
                        )

                    auth_request = AuthRequestMessage()
                    try:
                        auth_request = from_dict(
                            data_class=AuthRequestMessage,
                            data=message_json,
                            config=Config(cast=[Enum]),
                        )
                    except:
                        auth_response = AuthResponseMessage(
                            is_authenticated=False, message="Incorrect message format."
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(auth_response),
                        )
                        logging.error(
                            "%s: No username or password stated in the incoming authentication request, terminating connection.",
                            self.__address,
                        )
                        raise

                    if not self.__is_user_auth_correct_callback(
                        auth_request.username, auth_request.password_hash
                    ):
                        auth_response = AuthResponseMessage(
                            is_authenticated=False,
                            message="Incorrect username or password.",
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(auth_response),
                        )
                        logging.error(
                            "%s: Username or password is incorrect, terminating connection.",
                            self.__address,
                        )
                        raise AuthenticationFailureException(
                            f"{self.__address}: Username or password is incorrect, terminating connection."
                        )

                    is_authenticated = True

                    auth_response = AuthResponseMessage(
                        is_authenticated=True, message="Authentication successful."
                    )
                    send_message(
                        self.__applicant,
                        self.__address,
                        dataclasses.asdict(auth_response),
                    )

                    timestamp = datetime.datetime.today().strftime("%Y%m%d_%H%M%S")
                    username = auth_request.username
                    user_temp_folder_path = os.path.join(
                        self.__temp_directory,
                        timestamp + "_" + username + f"_{self.__address[1]}",
                    )
                    pathlib.Path(user_temp_folder_path).mkdir(
                        parents=True, exist_ok=True
                    )
                    logging.debug(
                        "%s: Created temporary folder %s.",
                        self.__address,
                        user_temp_folder_path,
                    )

                if message_json["type"] == TransmissionType.PROCEDURE_REQUEST:
                    if not is_authenticated:
                        procedure_response = ProcedureResponseMessage(
                            is_ready_for_procedure=False,
                            message="User is not authenticated.",
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(procedure_response),
                        )
                        logging.error(
                            "%s: User is not authenticated, terminating connection.",
                            self.__address,
                        )
                        raise UnexpectedMessageException(
                            f"{self.__address}: User is not authenticated, terminating connection."
                        )

                    procedure_request = ProcedureRequestMessage()
                    try:
                        procedure_request = from_dict(
                            data_class=ProcedureRequestMessage,
                            data=message_json,
                            config=Config(cast=[Enum]),
                        )
                    except:
                        procedure_response = ProcedureResponseMessage(
                            is_ready_for_procedure=False,
                            message="Incorrect message format.",
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(procedure_response),
                        )
                        logging.error(
                            "%s: No file size, CRC32, name or procedure stated in the incoming authentication request, terminating connection.",
                            self.__address,
                        )
                        raise

                    if not self.__is_procedure_allowed_for_user_callback(
                        username, procedure_request.procedure
                    ):
                        procedure_response = ProcedureResponseMessage(
                            is_ready_for_procedure=False,
                            message="User is not allowed to use selected procedure.",
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(procedure_response),
                        )
                        logging.error(
                            "%s: User is not allowed to use selected procedure, terminating connection.",
                            self.__address,
                        )
                        raise ProcedureApprovalException(
                            f"{self.__address}: User is not allowed to use selected procedure, terminating connection."
                        )

                    procedure_response = ProcedureResponseMessage(
                        is_ready_for_procedure=True,
                        message="Procedure approved, ready to receive files.",
                    )
                    send_message(
                        self.__applicant,
                        self.__address,
                        dataclasses.asdict(procedure_response),
                    )

                    procedure = procedure_request.procedure

                    file_size_bytes = procedure_request.file_size_bytes
                    received_file_path = os.path.join(
                        user_temp_folder_path, procedure_request.file_name
                    )

                    wait_and_receive_file(
                        self.__applicant,
                        self.__address,
                        received_file_path,
                        procedure_request.file_size_bytes,
                    )

                    data_crc32: int = 0
                    with open(received_file_path, "rb") as processed_file:
                        data = processed_file.read()
                        data_crc32 = binascii.crc32(data) & 0xFFFFFFFF
                        data_crc32_str = "%08X" % data_crc32
                        logging.info(
                            "%s: Received file CRC32: %s.",
                            self.__address,
                            data_crc32_str,
                        )

                    if data_crc32_str != procedure_request.file_crc32:
                        procedure_receipt = FileReceivingReceiptMessage(
                            is_received_correctly=False,
                            message=f"File is received incorrectly, received CRC32 {data_crc32} differs to provided CRC32 {procedure_request.file_crc32}.",
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(procedure_receipt),
                        )
                        logging.error(
                            "%s: File is received incorrectly, received CRC32 %s differs to provided CRC32 %s.",
                            self.__address,
                            data_crc32_str,
                            procedure_request.file_crc32,
                        )
                        raise ProcedureApprovalException(
                            f"{self.__address}: File is received incorrectly, received CRC32 {data_crc32} differs to provided CRC32 {procedure_request.file_crc32}."
                        )

                    file_size_bytes = os.path.getsize(received_file_path)
                    if file_size_bytes != procedure_request.file_size_bytes:
                        procedure_receipt = FileReceivingReceiptMessage(
                            is_received_correctly=False,
                            message=f"File is received incorrectly, received size {file_size_bytes} differs to provided size {procedure_request.file_size_bytes}.",
                        )
                        send_message(
                            self.__applicant,
                            self.__address,
                            dataclasses.asdict(procedure_receipt),
                        )
                        logging.error(
                            "%s: File is received incorrectly, received size %d differs to provided size %d.",
                            self.__address,
                            file_size_bytes,
                            procedure_request.file_size_bytes,
                        )
                        raise ProcedureApprovalException(
                            f"{self.__address}: File is received incorrectly, received size {file_size_bytes} differs to provided size {procedure_request.file_size_bytes}."
                        )

                    procedure_receipt = FileReceivingReceiptMessage(
                        is_received_correctly=True,
                        message="File is received correctly and being processed.",
                    )
                    send_message(
                        self.__applicant,
                        self.__address,
                        dataclasses.asdict(procedure_receipt),
                    )

                    file_paths = []
                    if procedure_request.file_type == FileType.SINGLE:
                        file_paths.append(received_file_path)
                    elif procedure_request.file_type == FileType.ARCHIVE:
                        with zipfile.ZipFile(received_file_path, "r") as zip_file:
                            zip_file.extractall(user_temp_folder_path)
                        os.remove(received_file_path)
                        file_paths = glob.glob(f"{user_temp_folder_path}/*")

                    for file_path in file_paths:
                        procedure_protocol = self.__configuration.procedures[procedure]
                        if type(procedure_protocol) is dict:
                            procedure_protocol: ProcedureProtocol = from_dict(
                                data_class=ProcedureProtocol,
                                data=self.__configuration.procedures[procedure],
                            )

                        operation = procedure_protocol.operation

                        if "<FILE_NAME>" in operation:
                            operation = operation.replace("<FILE_NAME>", file_path)

                        if "<FILE_COPY>" in operation:
                            file_copy_path = file_path
                            extension = pathlib.Path(file_copy_path).suffix
                            file_copy_path = file_copy_path.replace(
                                extension, "_copy" + extension
                            )
                            operation = operation.replace("<FILE_COPY>", file_copy_path)
                            shutil.copy(file_path, file_copy_path)

                        is_procedure_failed = False
                        for retry_counter in range(
                            procedure_protocol.max_repeats_if_failed
                        ):
                            self.__wait_until_file_is_accessible(
                                self.__address, file_path
                            )

                            logging.info(
                                "%s: Executing procedure '%s' operation: '%s'. Retry %d of %d.",
                                self.__address,
                                procedure_protocol.name,
                                operation,
                                (retry_counter + 1),
                                procedure_protocol.max_repeats_if_failed,
                            )

                            result = subprocess.run(
                                operation,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                shell=True,
                                text=True,
                                universal_newlines=True,
                                check=False,
                            )

                            if result.returncode in procedure_protocol.error_codes:
                                if (
                                    retry_counter
                                    != procedure_protocol.max_repeats_if_failed - 1
                                ):
                                    logging.warning(
                                        "%s: Procedure failed with return code %d and error message %s.",
                                        self.__address,
                                        result.returncode,
                                        result.stdout,
                                    )
                                    time.sleep(
                                        procedure_protocol.time_seconds_between_repeats
                                    )
                                    continue
                                else:
                                    is_procedure_failed = True
                                    break

                            else:
                                break

                        if is_procedure_failed:
                            procedure_receipt = ProcedureReceiptMessage(
                                is_processed_correctly=False,
                                message=f"Procedure failed with return code {result.returncode} and error message {result.stdout}.",
                            )
                            send_message(
                                self.__applicant,
                                self.__address,
                                dataclasses.asdict(procedure_receipt),
                            )
                            logging.error(
                                "%s: Procedure failed with return code %d and error message %s.",
                                self.__address,
                                result.returncode,
                                result.stdout,
                            )
                            raise ProcedureExecutionException(
                                f"{self.__address}: Procedure failed with return code {result.returncode} and error message {result.stdout}."
                            )

                    if procedure_request.file_type == FileType.ARCHIVE:
                        with zipfile.ZipFile(received_file_path, "w") as zip_file:
                            for file in file_paths:
                                zip_file.write(
                                    file,
                                    os.path.basename(file),
                                    compress_type=zipfile.ZIP_DEFLATED,
                                )

                    processed_file_size_bytes = os.path.getsize(received_file_path)
                    processed_data_crc32: int = 0
                    with open(received_file_path, "rb") as processed_file:
                        processed_data = processed_file.read()
                        processed_data_crc32 = (
                            binascii.crc32(processed_data) & 0xFFFFFFFF
                        )
                        processed_data_crc32_str = "%08X" % processed_data_crc32
                        logging.info(
                            "%s: Processed file CRC32: %s.",
                            self.__address,
                            processed_data_crc32_str,
                        )

                    procedure_receipt = ProcedureReceiptMessage(
                        is_processed_correctly=True,
                        message="File was successfully processed.",
                        file_crc32=processed_data_crc32_str,
                        file_size_bytes=processed_file_size_bytes,
                    )
                    send_message(
                        self.__applicant,
                        self.__address,
                        dataclasses.asdict(procedure_receipt),
                    )

                    send_file(self.__applicant, self.__address, processed_data)

        except ConnectionBrokenException:
            logging.info("%s: Applicant disconnected.", self.__address)

        except Exception as exception:
            logging.exception("%s: %s.", self.__address, str(exception))

        finally:
            try:
                self.__applicant.shutdown(socket.SHUT_RDWR)
            except OSError as exception:
                logging.warning(
                    "Caught low priority exception during applicant disconnect."
                )
                logging.exception(exception)

            self.__applicant.close()

            if self.__configuration.max_storage_period_hours == 0:
                if os.path.exists(user_temp_folder_path):
                    shutil.rmtree(user_temp_folder_path)
                    logging.debug(
                        "%s: Removed temporary folder %s.",
                        self.__address,
                        user_temp_folder_path,
                    )
