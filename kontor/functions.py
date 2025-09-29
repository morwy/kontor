#!/usr/bin/env python

import binascii
import json
import logging
import time
from kontor.defines import (
    MARKER_FILE_END,
    MARKER_FILE_START,
    MARKER_TRANSMISSION_END,
    MARKER_TRANSMISSION_START,
)

from kontor.exceptions import ConnectionBrokenException


def send_message(connection, address, message: dict):
    """
    Sends file through provided connection.

    Parameters:
        connection : socket.socket
            connection through where to send message
        address : tuple
            connection address for logging
        message : dict
            message to be sent
    """
    logging.debug("%s: Sending message: %s.", address, message)
    json_data_str = json.dumps(message)
    connection.sendall(
        bytes(
            MARKER_TRANSMISSION_START + json_data_str + MARKER_TRANSMISSION_END,
            encoding="utf-8",
        )
    )


def wait_and_receive_message(connection, address) -> dict:
    """
    Receives message that came from connection.
    Raises socket.timeout exception in case of timeout.

    Parameters:
        connection : socket.socket
            connection from where to expect message
        address : tuple
            connection address for logging

    Returns:
        message : dict
            received message of any type as dict
    """
    logging.debug("%s: Waiting for response.", address)

    message = {}

    raw_data = ""
    raw_data_binary = bytearray()

    marker_bytes = MARKER_TRANSMISSION_START.encode()
    max_marker_bytes_to_check = 5

    is_message_received = False
    while not is_message_received:
        #
        # Client will send TLS handshake to server even if server
        # does not run SSL based connection. Thus, ignore it.
        # Sometimes TLS handshake messages may have <> marker starter bytes.
        #
        byte = connection.recv(1)
        if byte == b'':
            raise ConnectionBrokenException(f"{address}: Connected party disconnected (1).")

        raw_data_size = len(raw_data)
        if (
            raw_data_size < max_marker_bytes_to_check
            and byte != marker_bytes[raw_data_size : raw_data_size + 1]
        ):
            raw_data_binary += bytearray(byte)
            raw_data = ""
            continue

        #
        # TODO: verify if this is still needed.
        #
        raw_data += byte.decode("utf-8")
        if len(raw_data) == 0:
            # socket returns 0 when other party calls socket.close().
            raise ConnectionBrokenException(f"{address}: Connected party disconnected (2).")

        if (
            raw_data.find(MARKER_TRANSMISSION_START) != -1
            and raw_data.find(MARKER_TRANSMISSION_END) != -1
        ):
            if len(raw_data_binary) > 0:
                discarded_data_str = (
                    binascii.hexlify(bytearray(raw_data_binary)).decode("utf-8").upper()
                )

                logging.warning(
                    "Discarding unsuitable data: %s (%d bytes).",
                    discarded_data_str,
                    len(raw_data_binary),
                )
                raw_data_binary.clear()

            message_start_marker_index = raw_data.find(MARKER_TRANSMISSION_START) + len(
                MARKER_TRANSMISSION_START
            )
            message_end_marker_index = raw_data.find(MARKER_TRANSMISSION_END)

            message_data = raw_data[message_start_marker_index:message_end_marker_index]
            message = json.loads(message_data)
            logging.debug("%s: Received message: %s.", address, message)

            message_end_index = message_end_marker_index + len(MARKER_TRANSMISSION_END)
            if len(raw_data) <= message_end_index:
                raw_data = ""
            else:
                raw_data = raw_data[message_end_index:]

            is_message_received = True

    return message


def send_file(connection, address, file: bytes):
    """
    Sends file through provided connection.

    Parameters:
        connection : socket.socket
            connection through where to send file
        address : tuple
            connection address for logging
        file : bytes
            file to be sent
    """
    logging.debug("%s: Sending file.", address)
    connection.send(MARKER_FILE_START)
    connection.sendall(file)
    connection.send(MARKER_FILE_END)


def wait_and_receive_file(
    connection, address, corrected_file_path: str, file_size_bytes: int
):
    """
    Waits for the file to arrive and saves to specified path.
    Raises socket.timeout exception in case of timeout.

    Parameters:
        connection : socket.socket
            connection from where to expect file
        address : tuple
            connection address for logging
        corrected_file_path : str
            path where to save received file
        file_size_bytes : int
            expected file size in bytes
    """
    with open(corrected_file_path, "wb") as processed_file:
        file_received_fully = False
        received_bytes = 0
        previous_percents = 0
        chunk_size_bytes = 256 * 1024

        file_start_time = time.time()
        while not file_received_fully:
            data = connection.recv(chunk_size_bytes)
            if len(data) == 0:
                break

            file_start_marker_length = len(MARKER_FILE_START)
            if data[:file_start_marker_length] == MARKER_FILE_START:
                data = data[file_start_marker_length:]

            file_end_marker_length = len(MARKER_FILE_END)
            if data[-file_end_marker_length:] == MARKER_FILE_END:
                file_received_fully = True
                data = data[:-file_end_marker_length]

            received_bytes += len(data)
            received_percents = int(100 / file_size_bytes * received_bytes)

            if received_percents % 10 == 0 and previous_percents != received_percents:
                previous_percents = received_percents
                logging.debug(
                    "%s: Receiving file, %d%% (%d / %d).",
                    address,
                    received_percents,
                    received_bytes,
                    file_size_bytes,
                )

            processed_file.write(data)

        file_upload_time = time.time() - file_start_time
        logging.debug(
            "%s: File receiving time is %.2f seconds.", address, file_upload_time
        )
