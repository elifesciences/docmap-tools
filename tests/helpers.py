import io
import os
import importlib


def delete_files_in_folder(folder, filter_out=None):
    file_list = os.listdir(folder)
    for file_name in file_list:
        file_path = os.path.join(folder, file_name)
        if filter_out and file_name in filter_out:
            continue
        elif os.path.isdir(file_path):
            # call recursively to delete file and folders inside a folder
            delete_files_in_folder(file_path)
            os.rmdir(file_path)
        elif os.path.isfile(file_path):
            os.remove(file_path)


def fixture_module_name(folder_names, filename):
    return ".".join(folder_names + [filename.rstrip(".py")])


def read_fixture(filename, mode="r"):
    folder_names = ["tests", "fixtures"]
    full_filename = os.path.join(os.sep.join(folder_names), filename)
    if full_filename.endswith(".py"):
        # import the fixture and return the value of expected
        module_name = fixture_module_name(folder_names, filename)
        mod = importlib.import_module(module_name)
        # assert expected exists before continuing
        assert hasattr(
            mod, "EXPECTED"
        ), "EXPECTED property not found in module {module_name}".format(
            module_name=module_name
        )
        return mod.EXPECTED
    else:
        kwargs = {"mode": mode}
        if mode == "r":
            kwargs["encoding"] = "utf-8"
        with io.open(full_filename, **kwargs) as file_fp:
            return file_fp.read()


def read_log_file_lines(log_file_path):
    "read log file lines as a list for using in test assertions"
    log_file_lines = []
    with open(log_file_path, "r") as open_file:
        for line in open_file:
            log_file_lines.append(line)
    return log_file_lines
