import os
import pathlib
import platform
import shutil

from kontor.applicant import BureauApplicant
from kontor.bureau import Bureau


def test_send_and_process_single_file(tmp_path):
    test_server_ip = "localhost"
    test_server_port = 5690
    test_username = "test_user"
    test_password = ""
    test_original_contents = (
        "this file is required to be modified and stamped in the stamp bureau"
    )
    test_modified_contents = "this file was modified and stamped in the stamp bureau"
    test_procedure_name = "test_procedure"

    if platform.system() == "Windows":
        test_procedure_operation = f"echo {test_modified_contents}><FILE_NAME>"
    elif platform.system() == "Darwin":
        test_procedure_operation = f'echo "{test_modified_contents}" > <FILE_NAME>'
    elif platform.system() == "Linux":
        test_procedure_operation = f'echo -n "{test_modified_contents}" > <FILE_NAME>'

    test_temp_path = os.path.join(tmp_path, "applicant")
    pathlib.Path(test_temp_path).mkdir(parents=True, exist_ok=True)
    test_file_path = os.path.join(test_temp_path, "test_file")
    with open(test_file_path, "w", encoding="utf-8") as test_file:
        test_file.write(test_original_contents)

    bureau = Bureau(tmp_path)
    bureau.add_procedure(test_procedure_name, test_procedure_operation, True)
    bureau.add_user(test_username, test_password, [test_procedure_name])
    bureau.start_async()

    applicant = BureauApplicant()
    applicant.process_file(
        server_ip_address=test_server_ip,
        server_port=test_server_port,
        username=test_username,
        password=test_password,
        procedure=test_procedure_name,
        file_path=test_file_path,
        overwrite_file=True,
    )

    bureau.shutdown()

    with open(test_file_path, "r", encoding="utf-8") as test_file:
        test_processed_file_contents = test_file.readlines()

    assert len(test_processed_file_contents) == 1
    assert test_processed_file_contents[0].rstrip("\n") == test_modified_contents


def test_send_and_process_multiple_files(tmp_path):
    test_server_ip = "localhost"
    test_server_port = 5690
    test_username = "test_user"
    test_password = ""
    test_original_contents = (
        "this file is required to be modified and stamped in the stamp bureau"
    )
    test_modified_contents = "this file was modified and stamped in the stamp bureau"
    test_procedure_name = "test_procedure"

    if platform.system() == "Windows":
        test_procedure_operation = f"echo {test_modified_contents}><FILE_NAME>"
    elif platform.system() == "Darwin":
        test_procedure_operation = f'echo "{test_modified_contents}" > <FILE_NAME>'
    elif platform.system() == "Linux":
        test_procedure_operation = f'echo -n "{test_modified_contents}" > <FILE_NAME>'

    test_temp_path = os.path.join(tmp_path, "applicant")
    pathlib.Path(test_temp_path).mkdir(parents=True, exist_ok=True)

    test_file_path_1 = os.path.join(test_temp_path, "test_file_1")
    with open(test_file_path_1, "w", encoding="utf-8") as test_file:
        test_file.write(test_original_contents)

    test_file_path_2 = test_file_path_1.replace("_1", "_2")
    shutil.copy(test_file_path_1, test_file_path_2)
    test_file_path_3 = test_file_path_1.replace("_1", "_3")
    shutil.copy(test_file_path_1, test_file_path_3)
    test_file_path_4 = test_file_path_1.replace("_1", "_4")
    shutil.copy(test_file_path_1, test_file_path_4)
    test_file_path_5 = test_file_path_1.replace("_1", "_5")
    shutil.copy(test_file_path_1, test_file_path_5)

    test_file_list = [
        test_file_path_1,
        test_file_path_2,
        test_file_path_3,
        test_file_path_4,
        test_file_path_5,
    ]

    bureau = Bureau(tmp_path)
    bureau.add_procedure(test_procedure_name, test_procedure_operation, True)
    bureau.add_user(test_username, test_password, [test_procedure_name])
    bureau.start_async()

    applicant = BureauApplicant()
    applicant.process_files(
        server_ip_address=test_server_ip,
        server_port=test_server_port,
        username=test_username,
        password=test_password,
        procedure=test_procedure_name,
        file_list=test_file_list,
        overwrite_file=True,
    )

    bureau.shutdown()

    for test_processed_file in test_file_list:
        with open(test_processed_file, "r", encoding="utf-8") as test_file:
            test_processed_file_contents = test_file.readlines()

        assert len(test_processed_file_contents) == 1
        assert test_processed_file_contents[0].rstrip("\n") == test_modified_contents
