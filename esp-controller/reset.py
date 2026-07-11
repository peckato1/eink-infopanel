Import("env")
import os
from platformio.builder.tools.pioupload import AutodetectUploadPort

platform = env.PioPlatform()
AutodetectUploadPort(env)
upload_port = env.subst("$UPLOAD_PORT")


def get_esptoolpy_reset_flags(resetmethod):
    return ["--before", "default_reset", "--after", "hard_reset"]


reset_flags = " ".join(get_esptoolpy_reset_flags(env.subst("$UPLOAD_RESETMETHOD")))
esptool = os.path.join(platform.get_package_dir("tool-esptoolpy"), "esptool.py")
esptool_cmd = f'$PYTHONEXE "{esptool}" --port {upload_port} {reset_flags} --no-stub run'

env.AddCustomTarget(name="reset", dependencies=None, actions=[esptool_cmd], title="Reset ESP8266", description="Resets the ESP8266 board")
