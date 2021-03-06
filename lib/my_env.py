"""
This module consolidates all local configuration for the script, including modulename collection for logfile name
setup and initializing the config file.
Also some application specific utilities find their home here.
"""

import configparser
import logging
import logging.handlers
import json
import os
import platform
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from pathvalidate import sanitize_filename, validate_filepath, validate_filename, ValidationError


def init_env(projectname, filename):
    """
    This function will initialize the environment: Find and return handle to config file and set-up logging.

    :param projectname: Name that will be used to find ini file in properties subdirectory.
    :param filename: Filename (__file__) of the calling script (for logfile).
    :return: config handle
    """
    modulename = get_modulename(filename)
    config = get_inifile(projectname)
    my_log = init_loghandler(modulename)
    my_log.info('Start Application')
    return config


def get_modulename(scriptname):
    """
    Modulename is required for logfile and for properties file.

    :param scriptname: Name of the script for which modulename is required. Use __file__.
    :return: Module Filename from the calling script.
    """
    # Extract calling application name
    (filepath, filename) = os.path.split(scriptname)
    (module, fileext) = os.path.splitext(filename)
    return module


def get_valid_path(parent, fn):
    """
    This function returns a valid path name for the parent path and the directory. It is an os.path.join, with
    additional validation on dir as a valid filename.
    We need to validate the filename, since 'some/name' will validate as a pathname, but needs to validate as filename.

    :param parent: parent directory, this must be a valid directory.
    :param fn: Directory or filename to add to the parent directory.
    :return: a valid parent/subdir path.
    """
    try:
        validate_filename(fn, platform='auto')
    except ValidationError:
        logging.info(f"Need to sanitize stream {fn} to {sanitize_filename(fn)}")
        attrib_fn = fn
        fn = sanitize_filename(fn)
        if not os.path.isfile(os.path.join(parent, f"{fn}_changed.txt")):
            with open(os.path.join(parent, f"{fn}_changed.txt"), 'w') as fh:
                msg = f"Name '{attrib_fn}' changed to '{fn}'"
                logging.info(msg)
                fh.write(msg)
    return os.path.join(parent, fn)


def init_loghandler(modulename):
    """
    This function initializes the loghandler. Logfilename consists of calling module name + computername.
    Format of the logmessage is specified in basicConfig function.

    :param modulename: The name of the module. Each module will create it's own logfile.
    :return: Log Handler
    """
    logdir = os.getenv("LOGDIR")
    loglevel = os.getenv("LOGLEVEL").upper()
    # Define logfileName
    logfn = "{module}_{host}.log".format(module=modulename, host=platform.node())
    logfile = os.path.join(logdir, logfn)
    # Configure the root logger
    logger = logging.getLogger()
    level = logging.getLevelName(loglevel)
    logger.setLevel(level)
    # Get logfiles of 1M
    maxbytes = 1024 * 1024
    rfh = logging.handlers.RotatingFileHandler(logfile, maxBytes=maxbytes, backupCount=5, encoding='utf8')
    # Create Formatter for file
    fmt_str = '%(asctime)s|%(name)s|%(module)s|%(funcName)s|%(lineno)d|%(levelname)s|%(message)s'
    formatter_file = logging.Formatter(fmt=fmt_str, datefmt='%d/%m/%Y|%H:%M:%S')
    # Add Formatter to Rotating File Handler
    rfh.setFormatter(formatter_file)
    # Add Handler to the logger
    logger.addHandler(rfh)
    # Configure Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter_console = logging.Formatter(fmt='%(asctime)s - %(module)s - %(funcName)s - %(lineno)d - %(levelname)s -'
                                              ' %(message)s',
                                          datefmt='%H:%M:%S')
    # Add Formatter to Console Handler
    ch.setFormatter(formatter_console)
    # logger.addHandler(ch)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    # logging.getLogger('asyncio.coroutines').setLevel(logging.WARNING)
    # logging.getLogger('websockets.server').setLevel(logging.WARNING)
    logging.getLogger('websockets.client').setLevel(logging.WARNING)
    logging.getLogger('websockets.protocol').setLevel(logging.WARNING)
    return logger


def get_inifile(projectname):
    """
    Read Project configuration ini file in subdirectory properties. Config ini filename is the projectname.
    The ini file is located in the properties module, which is sibling of the lib module.
    Environment settings defined in .env file are exported as well. The .env file needs to be in the project main
    directory.

    :param projectname: Name of the project.
    :return: Object reference to the inifile.
    """
    # Use Project Name as ini file.
    # Running Live
    # properties directory is sibling of lib directory.
    (filepath_lib, _) = os.path.split(__file__)
    (filepath, _) = os.path.split(filepath_lib)
    # configfile = filepath + "/properties/" + projectname + ".ini"
    configfile = os.path.join(filepath, 'properties', "{p}.ini".format(p=projectname))
    ini_config = configparser.ConfigParser()
    try:
        f = open(configfile, encoding='utf-8')
        ini_config.read_file(f)
        f.close()
    except FileNotFoundError:
        # If no Config file defined, then return empty dictionary.
        ini_config = {}
    envfile = os.path.join(filepath, ".env")
    load_dotenv(dotenv_path=envfile)
    return ini_config


def dump_structure(struct, path, filename, sort_keys=False):
    """
    This function takes a python structure, dumps it to a json string and saves the result in a file or the specified
    directory.
    This function has an attribute 'path_dict'.
    Filename/Path validation is done using pathvalidate. This seems a better approach compared to the slugify function.
    Slugify will slug names even if corresponding filename is valid.

    :param struct: Python structure that need to be written to file.
    :param path: Path of the resulting file. If path does not exist it will be created.
    :param filename: Filename of the required file.
    :param sort_keys: If set then sort on Keys. Default False.
    :return:
    """
    try:
        validate_filepath(path, platform='auto')
    except ValidationError as e:
        logging.critical(f"Invalid path {path}: {e}")
        return
    if not os.path.isdir(path):
        os.mkdir(path)
    struct_str = json.dumps(struct, ensure_ascii=False, indent=2, sort_keys=sort_keys)
    try:
        validate_filename(filename, platform='auto')
    except ValidationError:
        filename = sanitize_filename(filename)
    with open(os.path.join(path, filename), 'w', encoding='utf-8') as fh:
        fh.write(struct_str)
    return


def run_script(path, script_name, *args):
    """
    This function will run a python script with arguments.

    :param path: Full path to the script.
    :param script_name: Name of the script. Include .py if this is the script extension.
    :param args: List of script arguments.
    :return:
    """
    script_path = os.path.join(path, script_name)
    cmd = [sys.executable, script_path] + list(args)
    logging.debug(cmd)
    subprocess.run(cmd, env=os.environ.copy())
    return


class LoopInfo:
    """
    This class handles a FOR loop information handling.
    """

    def __init__(self, attribname, triggercnt):
        """
        Initialization of FOR loop information handling. Start message is printed for attribname. Information progress
        message will be printed for every triggercnt iterations.

        :param attribname:
        :param triggercnt:
        :return:
        """
        self.rec_cnt = 0
        self.loop_cnt = 0
        self.attribname = attribname
        self.triggercnt = triggercnt
        curr_time = datetime.now().strftime("%H:%M:%S")
        print("{0} - Start working on {1}".format(curr_time, str(self.attribname)))
        return

    def info_loop(self):
        """
        Check number of iterations. Print message if number of iterations greater or equal than triggercnt.

        :return: Count
        """
        self.rec_cnt += 1
        self.loop_cnt += 1
        if self.loop_cnt >= self.triggercnt:
            curr_time = datetime.now().strftime("%H:%M:%S")
            print("{0} - {1} {2} handled".format(curr_time, str(self.rec_cnt), str(self.attribname)))
            self.loop_cnt = 0
        return self.rec_cnt

    def end_loop(self):
        curr_time = datetime.now().strftime("%H:%M:%S")
        print("{0} - {1} {2} handled - End.\n".format(curr_time, str(self.rec_cnt), str(self.attribname)))
        return self.rec_cnt
