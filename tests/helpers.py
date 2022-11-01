import io
import os
import importlib


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
