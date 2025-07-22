import re
import logging
import sys
import config
import os
import stdlib_list # Requires: pip install stdlib_list

logger = logging.getLogger(__name__)

# --- Standard Library Modules (Python 3.10) ---
# Using stdlib_list for a more reliable list
try:
    STDLIB_MODULES = set(stdlib_list.stdlib_list("3.10"))
    logger.info("Successfully loaded Python 3.10 standard library list.")
except Exception as e:
    logger.warning(f"Could not load stdlib_list for Python 3.10, using a basic fallback list: {e}")
    # Fallback basic list if stdlib_list fails or is not installed
    STDLIB_MODULES = {
        '__future__', 'abc', 'aifc', 'argparse', 'array', 'ast', 'asyncio', 'atexit',
        'audioop', 'base64', 'bdb', 'binascii', 'bisect', 'builtins', 'bz2', 'calendar',
        'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs', 'codeop', 'collections',
        'colorsys', 'compileall', 'concurrent', 'configparser', 'contextlib', 'contextvars',
        'copy', 'copyreg', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime',
        'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email', 'encodings',
        'ensurepip', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
        'fnmatch', 'formatter', 'fractions', 'ftplib', 'functools', 'gc', 'getopt',
        'getpass', 'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq',
        'hmac', 'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib',
        'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3',
        'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal',
        'math', 'mimetypes', 'mmap', 'modulefinder', 'multiprocessing', 'netrc',
        'nis', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev',
        'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil',
        'platform', 'plistlib', 'poplib', 'posix', 'pprint', 'profile', 'pstats',
        'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'pydoc_data', 'pyexpat', 'queue',
        'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
        'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
        'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'sqlite3',
        'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess', 'sunau',
        'symbol', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib',
        'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time', 'timeit', 'tkinter',
        'token', 'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle',
        'turtledemo', 'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid',
        'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'wsgiref', 'xdrlib', 'xml',
        'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib', 'zoneinfo'
    }

def setup_logging():
    """Configures logging to file and console."""
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    log_file_path = os.path.join(config.OUTPUT_DIR, 'agent_run.log')

    # Avoid adding handlers multiple times if called again
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.info("Logging setup complete.")
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("docker").setLevel(logging.INFO)

def extract_python_code(text: str) -> str | None:
    """Extracts the first Python code block from markdown formatted text."""
    # ... (keep the implementation from the previous version) ...
    if not text:
        return None

    pattern_python = r"```python\s*([\s\S]+?)\s*```"
    match_python = re.search(pattern_python, text, re.MULTILINE)
    if match_python:
        logger.debug("Extracted code using ```python block.")
        return match_python.group(1).strip()

    pattern_generic = r"```\s*([\s\S]+?)\s*```"
    match_generic = re.search(pattern_generic, text, re.MULTILINE)
    if match_generic:
        code_candidate = match_generic.group(1).strip()
        if "def " in code_candidate or "import " in code_candidate or "print(" in code_candidate or "=" in code_candidate:
             logger.warning("Extracted code using generic ``` block. Assuming Python.")
             return code_candidate
        else:
             logger.warning("Found generic ``` block, but content doesn't strongly resemble Python.")
             return None

    if "def " in text or "import " in text or "print(" in text or "=" in text:
         lines = text.strip().split('\n')
         if len(lines) > 0 and not lines[0].lower().startswith("```"):
             logger.warning("No markdown code blocks found. Assuming entire response might be code.")
             return text.strip()

    logger.error("Could not extract Python code from the provided text.")
    return None


def save_code_to_file(code: str, filename: str):
    """Saves the given code string to a file in the output directory."""
    # ... (keep the implementation from the previous version) ...
    filepath = os.path.join(config.OUTPUT_DIR, filename)
    try:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True) # Ensure dir exists
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        logger.info(f"Code saved successfully to {filepath}")
        return filepath
    except IOError as e:
        logger.error(f"Failed to save code to {filepath}: {e}")
        return None

def parse_imports(code_string: str) -> set[str]:
    """
    Parses Python code to find imported top-level package names, excluding standard library modules.
    """
    # Regex for `import package` or `import package as alias`
    import_pattern = r"^\s*import\s+([\w.]+)(?:\s+as\s+\w+)?.*"
    # Regex for `from package import ...` or `from package.module import ...`
    from_pattern = r"^\s*from\s+([\w.]+)\s+import\s+.*"

    found_modules = set()

    for line in code_string.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        import_match = re.match(import_pattern, line)
        if import_match:
            # For 'import a.b.c', the top-level package is 'a'
            top_level_module = import_match.group(1).split('.')[0]
            found_modules.add(top_level_module)
            continue # Process next line

        from_match = re.match(from_pattern, line)
        if from_match:
            # For 'from a.b import c', the top-level package is 'a'
            top_level_module = from_match.group(1).split('.')[0]
            found_modules.add(top_level_module)
            continue # Process next line

    # Filter out standard library modules and empty strings
    external_packages = {
        mod for mod in found_modules
        if mod and mod not in STDLIB_MODULES
    }

    if external_packages:
        logger.info(f"Parsed external dependencies: {external_packages}")
    else:
        logger.info("No external dependencies parsed.")

    return external_packages