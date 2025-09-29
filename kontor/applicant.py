#!/usr/bin/env python

import binascii
import dataclasses
import datetime
import hashlib
import logging
import os
import pathlib
import socket
import ssl
import sys
import time
import uuid
import zipfile
from enum import Enum

import pkg_resources
from dacite import Config, from_dict

from kontor.defines import FileType
from kontor.exceptions import (
    AuthenticationFailureException,
    EmptyFileListException,
    FileTransmissionException,
    ProcedureApprovalException,
    ProcedureExecutionException,
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
    FileReceivingReceiptMessage,
    ProcedureReceiptMessage,
    ProcedureRequestMessage,
    ProcedureResponseMessage,
)


class BureauApplicant:
    def __init__(
        self,
        max_connection_retries: int = 6,
        time_seconds_between_connection_retries: int = 10,
        communication_timeout_seconds: int = 30,
        file_transfer_timeout_seconds: int = 300,
        enable_file_logging: bool = False,
    ):
        self.__address = ()
        self.__socket = None
        self.__ssl_context = ssl.create_default_context()

        self.__working_directory = os.getcwd()

        self.__max_connection_retries = max_connection_retries
        self.__time_seconds_between_connection_retries = (
            time_seconds_between_connection_retries
        )

        self.__communication_timeout_seconds = communication_timeout_seconds
        self.__file_transfer_timeout_seconds = file_transfer_timeout_seconds

        #
        # Enable logging both to file and stdout.
        #
        handlers = [logging.StreamHandler()]

        if enable_file_logging:
            log_directory = os.path.dirname(os.path.realpath(__file__))
            timestamp = datetime.datetime.today().strftime("%Y%m%d_%H%M%S")
            filename = timestamp + "_applicant.log"
            filepath = os.path.join(log_directory, filename)
            handlers.append(logging.FileHandler(filepath))

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s:%(levelname)s %(message)s",
            handlers=handlers,
        )

        try:
            kontor_version = pkg_resources.get_distribution("kontor").version
            logging.info(
                "Initializing the kontor applicant of version %s.", kontor_version
            )
        except pkg_resources.DistributionNotFound:
            logging.warning("Kontor applicant version was not found.")

    def __connect(self, server_ip_address: str, server_port: int):
        is_server_use_ssl = False
        try:
            #
            # Timeout in ssl.get_server_certificate() appeared only in Python 3.10.
            #
            if sys.version_info[1] > 10:
                _ = ssl.get_server_certificate(
                    (server_ip_address, server_port), timeout=1
                )
            else:
                _ = ssl.get_server_certificate((server_ip_address, server_port))

            is_server_use_ssl = True
        except Exception as exception:
            logging.info(
                "Server does not use SSL, falling back to non-SSL connection. Exception message: %s.",
                exception,
            )

        socket.setdefaulttimeout(self.__communication_timeout_seconds)

        current_retry = 0
        try:
            for current_retry in range(self.__max_connection_retries):
                if current_retry == 0:
                    logging.info("Connecting to %s:%d.", server_ip_address, server_port)
                else:
                    logging.info(
                        "Connecting to %s:%d (Retry %d out of %d).",
                        server_ip_address,
                        server_port,
                        current_retry,
                        self.__max_connection_retries,
                    )

                non_ssl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                non_ssl_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                non_ssl_socket.settimeout(self.__communication_timeout_seconds)
                non_ssl_socket.connect((server_ip_address, server_port))

                if is_server_use_ssl:
                    self.__socket = self.__ssl_context.wrap_socket(
                        non_ssl_socket, server_hostname=server_ip_address
                    )
                else:
                    self.__socket = non_ssl_socket

                break

        except socket.timeout:
            if current_retry == self.__max_connection_retries - 1:
                raise

            time.sleep(self.__time_seconds_between_connection_retries)

        self.__address = (
            self.__socket.getsockname()[0],
            self.__socket.getsockname()[1],
        )

    def __disconnect(self):
        logging.info("%s: Closing the connection.", self.__address)
        self.__socket.shutdown(socket.SHUT_RDWR)
        self.__socket.close()

    def __authenticate(self, username: str, password: str):
        logging.info("%s: Authenticating '%s' user.", self.__address, username)

        password_hash = hashlib.sha512(password.encode("utf-8")).hexdigest()
        auth_request = AuthRequestMessage(
            username=username, password_hash=password_hash
        )

        send_message(self.__socket, self.__address, dataclasses.asdict(auth_request))
        response_json_data = wait_and_receive_message(self.__socket, self.__address)
        auth_response = from_dict(
            data_class=AuthResponseMessage,
            data=response_json_data,
            config=Config(cast=[Enum]),
        )

        if auth_response.is_authenticated:
            logging.info("%s: Authentication succeed.", self.__address)
        else:
            logging.error(
                "%s: Authentication failed with error %s.",
                self.__address,
                auth_response.message,
            )
            raise AuthenticationFailureException(
                f"Authentication failed with error {auth_response.message}."
            )

    def __send_file_for_processing(
        self, procedure: str, file_path: str, file_type: FileType
    ):
        file_name = os.path.basename(file_path)
        file_size_bytes = os.path.getsize(file_path)

        with open(file_path, "rb") as file:
            file_data = file.read()

        file_data_crc32 = binascii.crc32(file_data) & 0xFFFFFFFF
        file_data_crc32_str = "%08X" % file_data_crc32

        procedure_request = ProcedureRequestMessage(
            procedure=procedure,
            file_type=file_type,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            file_crc32=file_data_crc32_str,
        )

        send_message(
            self.__socket, self.__address, dataclasses.asdict(procedure_request)
        )
        response_json_data = wait_and_receive_message(self.__socket, self.__address)
        procedure_response = from_dict(
            data_class=ProcedureResponseMessage,
            data=response_json_data,
            config=Config(cast=[Enum]),
        )

        if procedure_response.is_ready_for_procedure:
            logging.info("%s: Procedure was approved.", self.__address)
        else:
            logging.error(
                "%s: Procedure was declined with error %s.",
                self.__address,
                procedure_response.message,
            )
            raise ProcedureApprovalException(
                f"{self.__address}: Procedure was declined with error {procedure_response.message}."
            )

        send_file(self.__socket, self.__address, file_data)
        response_json_data = wait_and_receive_message(self.__socket, self.__address)
        file_receiving_receipt = from_dict(
            data_class=FileReceivingReceiptMessage,
            data=response_json_data,
            config=Config(cast=[Enum]),
        )

        if file_receiving_receipt.is_received_correctly:
            logging.info("%s: File was received correctly.", self.__address)
        else:
            logging.error(
                "%s: File was received with error %s.",
                self.__address,
                procedure_response.message,
            )
            raise FileTransmissionException(
                f"{self.__address}: File was received with error {procedure_response.message}."
            )

    def __wait_and_receive_result_file(self, file_path: str, overwrite_file: bool):
        self.__socket.settimeout(self.__file_transfer_timeout_seconds)

        request_json_data = wait_and_receive_message(self.__socket, self.__address)
        procedure_receipt = from_dict(
            data_class=ProcedureReceiptMessage,
            data=request_json_data,
            config=Config(cast=[Enum]),
        )

        if procedure_receipt.is_processed_correctly:
            logging.info(
                "%s: Procedure succeed, processed file is coming.", self.__address
            )
        else:
            logging.error(
                "%s: Procedure failed with error %s.",
                self.__address,
                procedure_receipt.message,
            )
            raise ProcedureExecutionException(
                f"{self.__address}: Procedure failed with error {procedure_receipt.message}."
            )

        self.__socket.settimeout(self.__communication_timeout_seconds)

        corrected_file_path = file_path
        if not overwrite_file:
            extension = pathlib.Path(corrected_file_path).suffix
            corrected_file_path = corrected_file_path.replace(
                extension, "_processed" + extension
            )

        wait_and_receive_file(
            self.__socket,
            self.__address,
            corrected_file_path,
            procedure_receipt.file_size_bytes,
        )

        data_crc32: int = 0
        with open(corrected_file_path, "rb") as processed_file:
            data = processed_file.read()
            data_crc32 = binascii.crc32(data) & 0xFFFFFFFF
            data_crc32_str = "%08X" % data_crc32
            logging.debug(
                "%s: Received file CRC32: %s.", self.__address, data_crc32_str
            )

        if data_crc32_str != procedure_receipt.file_crc32:
            logging.error(
                "%s: File is received incorrectly, received CRC32 %s differs to provided CRC32 %s.",
                self.__address,
                data_crc32_str,
                procedure_receipt.file_crc32,
            )
            raise ProcedureApprovalException(
                f"{self.__address}: File is received incorrectly, received CRC32 {data_crc32} differs to provided CRC32 {procedure_receipt.file_crc32}."
            )

        file_size_bytes = os.path.getsize(corrected_file_path)
        if file_size_bytes != procedure_receipt.file_size_bytes:
            logging.error(
                "%s: File is received incorrectly, received size %d differs to provided size %d.",
                self.__address,
                file_size_bytes,
                procedure_receipt.file_size_bytes,
            )
            raise ProcedureApprovalException(
                f"{self.__address}: File is received incorrectly, received size {file_size_bytes} differs to provided size {procedure_receipt.file_size_bytes}."
            )

        logging.info(
            "%s: Processed file was received successfully, disconnecting.",
            self.__address,
        )
        self.__disconnect()

    def __process_file(
        self,
        server_ip_address: str,
        server_port: int,
        username: str,
        password: str,
        procedure: str,
        file_path: str,
        file_type: FileType,
        overwrite_file: bool = True,
        max_retries_if_failed: int = 5,
        seconds_between_retries: int = 10,
    ):
        for retry_index in range(max_retries_if_failed):
            try:
                self.__connect(server_ip_address, server_port)
                self.__authenticate(username, password)
                self.__send_file_for_processing(procedure, file_path, file_type)
                self.__wait_and_receive_result_file(file_path, overwrite_file)
                break

            except Exception as exception:
                logging.error("Caught exception: '%s'.", type(exception))
                if retry_index == (max_retries_if_failed - 1):
                    logging.error(
                        "Reached maximum attempts of retries (%d), failing now.",
                        max_retries_if_failed,
                    )
                    logging.exception(exception)
                    raise

                time.sleep(seconds_between_retries)

    def process_file(
        self,
        server_ip_address: str,
        server_port: int,
        username: str,
        password: str,
        procedure: str,
        file_path: str,
        overwrite_file: bool = True,
        max_retries_if_failed: int = 5,
        seconds_between_retries: int = 10,
    ):
        self.__process_file(
            server_ip_address,
            server_port,
            username,
            password,
            procedure,
            file_path,
            FileType.SINGLE,
            overwrite_file,
            max_retries_if_failed,
            seconds_between_retries,
        )

    def process_files(
        self,
        server_ip_address: str,
        server_port: int,
        username: str,
        password: str,
        procedure: str,
        file_list: list,
        overwrite_file: bool = True,
        max_retries_if_failed: int = 5,
        seconds_between_retries: int = 10,
    ):
        if len(file_list) == 0:
            raise EmptyFileListException("Provided file list is empty!")

        if len(file_list) == 1:
            logging.info("Only one file provided, redirecting to other function.")
            self.process_file(
                server_ip_address,
                server_port,
                username,
                password,
                procedure,
                file_list[0],
                overwrite_file,
                max_retries_if_failed,
                seconds_between_retries,
            )
            return

        zip_file_path = os.path.join(
            self.__working_directory, str(uuid.uuid4()) + ".zip"
        )

        logging.info(
            "Multiple files were provided, zipping them into archive: %s.",
            zip_file_path,
        )

        try:
            with zipfile.ZipFile(zip_file_path, "w") as zip_file:
                for file in file_list:
                    zip_file.write(
                        file, os.path.basename(file), compress_type=zipfile.ZIP_DEFLATED
                    )

            self.__process_file(
                server_ip_address,
                server_port,
                username,
                password,
                procedure,
                zip_file_path,
                FileType.ARCHIVE,
                overwrite_file,
                max_retries_if_failed,
                seconds_between_retries,
            )

            with zipfile.ZipFile(zip_file_path, "r") as zip_file:
                for name in zip_file.namelist():
                    original_filepaths = [s for s in file_list if s.__contains__(name)]
                    for original_filepath in original_filepaths:
                        logging.info(
                            "Unzipping file %s to %s.", name, original_filepath
                        )

                        original_folder_path = pathlib.Path(
                            original_filepath
                        ).parent.absolute()

                        zip_file.extract(name, original_folder_path)
        finally:
            if os.path.exists(zip_file_path):
                logging.info("Deleting zip archive %s.", zip_file_path)
                os.remove(zip_file_path)
