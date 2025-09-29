#!/usr/bin/env python

import dataclasses
import hashlib
import json
import logging
import os
import pathlib
import socket
import ssl
import threading
import time
from logging.handlers import TimedRotatingFileHandler
from dacite import from_dict

import pkg_resources

from kontor.clerk import Clerk
from kontor.exceptions import (
    MissingWorkingDirectoryException,
    ProcedureAlreadyPresentException,
    ServerCertificateKeyMissingException,
    ServerCertificateMissingException,
    ServerStartTimeoutException,
)
from kontor.structures import (
    ApplicantDossier,
    BureauOperationProtocol,
    ProcedureProtocol,
)


class Bureau:
    def __init__(self, working_folder_path: str):
        self.__socket: socket.socket = None
        self.__ssl_context = None
        self.__configuration: BureauOperationProtocol = BureauOperationProtocol()
        self.__is_server_started = False
        self.__is_bureau_shutting_down = False

        self.__server_thread: threading.Thread = None
        self.__client_threads = []
        self.__clerks = []

        self.__working_directory = str(working_folder_path)
        pathlib.Path(self.__working_directory).mkdir(parents=True, exist_ok=True)

        self.__temp_directory = os.path.join(self.__working_directory, "temp")
        pathlib.Path(self.__temp_directory).mkdir(parents=True, exist_ok=True)

        #
        # Enable daily logging both to file and stdout.
        #
        log_directory = os.path.join(self.__working_directory, "logs")
        pathlib.Path(log_directory).mkdir(parents=True, exist_ok=True)

        filename = "bureau.log"
        filepath = os.path.join(log_directory, filename)

        handler = TimedRotatingFileHandler(filepath, when="midnight", backupCount=60)
        handler.suffix = "%Y%m%d"

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s:%(levelname)s %(message)s",
            handlers=[handler, logging.StreamHandler()],
        )

        try:
            kontor_version = pkg_resources.get_distribution("kontor").version
            logging.info(
                "Initializing the kontor bureau of version %s.", kontor_version
            )
        except pkg_resources.DistributionNotFound:
            logging.warning("Kontor bureau version was not found.")

        self.__parse_configuration_json_file()

        #
        # Try loading SSL certificate.
        #
        is_certificate_loaded = False
        certificate_path = self.__configuration.certificate_path
        if certificate_path:
            if os.path.exists(certificate_path):
                is_certificate_loaded = True
            else:
                certificate_path = os.path.join(
                    self.__working_directory, self.__configuration.certificate_path
                )
                is_certificate_loaded = os.path.exists(certificate_path)

        if self.__configuration.forced_ssl_usage and not is_certificate_loaded:
            logging.critical("Server certificate file is missing!")
            raise ServerCertificateMissingException(
                "Server certificate file is missing!"
            )

        is_certificate_key_loaded = False
        certificate_key_path = self.__configuration.certificate_key_path
        if certificate_key_path:
            if os.path.exists(certificate_key_path):
                is_certificate_key_loaded = True
            else:
                certificate_key_path = os.path.join(
                    self.__working_directory, self.__configuration.certificate_key_path
                )
                is_certificate_key_loaded = os.path.exists(certificate_key_path)

        if self.__configuration.forced_ssl_usage and not is_certificate_key_loaded:
            logging.critical("Server certificate key file is missing!")
            raise ServerCertificateKeyMissingException(
                "Server certificate key file is missing!"
            )

        if is_certificate_loaded and is_certificate_key_loaded:
            self.__ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.__ssl_context.load_cert_chain(
                certfile=certificate_path, keyfile=certificate_key_path
            )

            logging.info(
                "SSL certificate '%s' and its key '%s' were loaded successfully.",
                certificate_path,
                certificate_key_path,
            )
        else:
            logging.info("No SSL certificate was loaded.")

    def __parse_configuration_json_file(self, configuration_filepath=None):
        """
        Try to locate configuration file in the working directory.
        """
        if configuration_filepath is None:
            configuration_filepath = os.path.join(
                self.__working_directory, "server_configuration.json"
            )

        #
        # Use default settings if no file was found. Create file with default settings.
        #
        if not os.path.exists(configuration_filepath):
            self.__save_configuration_to_json_file()
            return

        #
        # Read configuration JSON.
        #
        with open(configuration_filepath, "r", encoding="utf-8") as json_file:
            configuration_json = json.load(json_file)

        self.__configuration = from_dict(
            data_class=BureauOperationProtocol,
            data=configuration_json,
        )

    def __save_configuration_to_json_file(self, configuration_filepath=None):
        if configuration_filepath is None:
            configuration_filepath = os.path.join(
                self.__working_directory, "server_configuration.json"
            )

        with open(configuration_filepath, "w", encoding="utf-8") as file:
            json.dump(
                dataclasses.asdict(self.__configuration),
                file,
                ensure_ascii=False,
                indent=4,
            )

    def __is_user_auth_correct(self, username: str, password_hash: str) -> bool:
        """
        Reading and parsing file every time function is called for loading file changes.
        Should be fine with small user databases.
        """
        user_db_filepath = os.path.join(self.__working_directory, "server_users.json")
        with open(user_db_filepath, "r", encoding="utf-8") as json_file:
            user_db_json = json.load(json_file)

        for user in user_db_json:
            if username == user["username"]:
                if password_hash == user["password_hash"]:
                    return True

        return False

    def __is_procedure_allowed_for_user(self, username: str, procedure: str) -> bool:
        """
        Reading and parsing file every time function is called for loading file changes.
        Should be fine with small user databases.
        """
        user_db_filepath = os.path.join(self.__working_directory, "server_users.json")
        with open(user_db_filepath, "r", encoding="utf-8") as json_file:
            user_db_json = json.load(json_file)

        for user in user_db_json:
            if username == user["username"]:
                if procedure in user["allowed_procedures"]:
                    return True

        return False

    def __service_applicant_in_new_cubicle(self, clerk: Clerk, address):
        clerk.provide_service()

        #
        # Automatically remove itself from list of client threads.
        #
        self.__clerks.remove(clerk)
        self.__client_threads.remove(threading.current_thread())

        logging.info("%s: Thread for connection was closed.", address)

    def add_user(self, username: str, password: str, allowed_procedures: list):
        if not os.path.exists(self.__working_directory):
            raise MissingWorkingDirectoryException(
                "Working directory is not set, aborting start."
            )

        if not os.path.exists(self.__temp_directory):
            raise MissingWorkingDirectoryException(
                "Temporary directory is not set, aborting start."
            )

        new_user = ApplicantDossier()
        new_user.username = username
        new_user.password_hash = hashlib.sha512(password.encode("utf-8")).hexdigest()
        new_user.allowed_procedures = allowed_procedures

        user_db_json = []
        user_db_filepath = os.path.join(self.__working_directory, "server_users.json")
        if os.path.exists(user_db_filepath):
            with open(user_db_filepath, "r", encoding="utf-8") as json_file:
                user_db_json = json.load(json_file)

        user_db_json.append(dataclasses.asdict(new_user))

        with open(user_db_filepath, "w", encoding="utf-8") as file:
            json.dump(
                user_db_json,
                file,
                ensure_ascii=False,
                indent=4,
            )

    def add_procedure(self, name: str, operation: str, overwrite: bool = False):
        if not os.path.exists(self.__working_directory):
            raise MissingWorkingDirectoryException(
                "Working directory is not set, aborting start."
            )

        if not os.path.exists(self.__temp_directory):
            raise MissingWorkingDirectoryException(
                "Temporary directory is not set, aborting start."
            )

        if not overwrite and name in self.__configuration.procedures:
            raise ProcedureAlreadyPresentException(
                f"Procedure {name} is already present in configuration."
            )

        procedure = ProcedureProtocol()
        procedure.name = name
        procedure.operation = operation
        procedure.error_codes = [1]

        self.__configuration.procedures[name] = procedure
        self.__save_configuration_to_json_file()

    def start_async(self):
        self.__server_thread = threading.Thread(target=self.start, daemon=True)
        self.__server_thread.start()

        max_seconds_to_wait = 30
        timeout = time.time() + max_seconds_to_wait
        while not self.__is_server_started:
            time.sleep(1)

            if time.time() >= timeout:
                raise ServerStartTimeoutException(
                    f"Failed to start server in {max_seconds_to_wait} seconds!"
                )

    def start(self):
        if not os.path.exists(self.__working_directory):
            logging.critical("Working directory is not set, aborting start.")
            raise MissingWorkingDirectoryException(
                "Working directory is not set, aborting start."
            )

        if not os.path.exists(self.__temp_directory):
            logging.critical("Temporary directory is not set, aborting start.")
            raise MissingWorkingDirectoryException(
                "Temporary directory is not set, aborting start."
            )

        logging.info(
            "Opening bureau's reception at %s:%d.",
            self.__configuration.ip_address,
            self.__configuration.port,
        )

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.bind((self.__configuration.ip_address, self.__configuration.port))
        self.__socket.listen(self.__configuration.max_parallel_connections)
        self.__socket.settimeout(0.5)

        logging.info("Starting to listen for incoming connections.")

        self.__is_server_started = True
        while not self.__is_bureau_shutting_down:
            try:
                client_socket, address = self.__socket.accept()

                logging.info("New incoming connection from %s.", address)

                client_socket.settimeout(
                    self.__configuration.client_idle_timeout_seconds
                )
                selected_client_socket = client_socket

                if self.__ssl_context is not None:
                    selected_client_socket = self.__ssl_context.wrap_socket(
                        client_socket,
                        server_side=True,
                    )

                clerk = Clerk(
                    self.__configuration,
                    self.__temp_directory,
                    selected_client_socket,
                    address,
                    self.__is_user_auth_correct,
                    self.__is_procedure_allowed_for_user,
                )

                thread = threading.Thread(
                    target=self.__service_applicant_in_new_cubicle,
                    args=(
                        clerk,
                        address,
                    ),
                )
                thread.start()
                self.__clerks.append(clerk)
                self.__client_threads.append(thread)

            except socket.timeout:
                #
                # Ignore socket.timeout exception.
                #
                time.sleep(0.5)

            except Exception as exception:
                logging.info(
                    "Caught exception during waiting for new connections. Exception %s.",
                    str(exception),
                )
                time.sleep(0.5)

    def shutdown(self):
        """
        Gracefully shuts down the bureau, waiting for clerks to complete their job.
        Max wait is defined by bureau protocol.
        """
        logging.info("Shutting down the bureau.")

        self.__is_bureau_shutting_down = True

        for clerk in self.__clerks:
            clerk.notify_about_shutdown()

        grace_shutdown_start_time = time.process_time()
        while (
            len(self.__client_threads) > 0
            and (time.process_time() - grace_shutdown_start_time)
            >= self.__configuration.max_grace_shutdown_timeout_seconds
        ):
            logging.info(
                "Waiting for %d thread to complete their jobs (max wait %d seconds).",
                len(self.__client_threads),
                self.__configuration.max_grace_shutdown_timeout_seconds,
            )
            time.sleep(5)

        #
        # Somewhat weird way of stopping endlessly waiting socket.accept.
        # TODO: is it still needed?
        #
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
            (self.__configuration.ip_address, self.__configuration.port)
        )
        self.__socket.close()

        if self.__server_thread is not None:
            logging.info(
                "Server is running in async mode, waiting for thread to finish."
            )
            self.__server_thread.join()

        logging.info("Shutdown complete.")
