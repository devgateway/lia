import logging, os, json
from time import time

from .config import get_config, MissingConfigValue

_log = logging.getLogger(__name__)

class CacheExpiredError(Exception):
    pass

def _get_cache_file_name():
    basename = "lia.json"
    try:
        return os.path.join(os.environ["XDG_CACHE_HOME"], basename)
    except KeyError:
        return os.path.join(os.environ["HOME"], ".cache", basename)

def load_cached():
    try:
        cfg = get_config()
        cache_time = cfg.cache_time
    except MissingConfigValue:
        cache_time = 10800

    filename = _get_cache_file_name()
    _log.info("Loading cached data from %s" % filename)

    try:
        stat_info = os.stat(filename)
        if time() - stat_info.st_mtime > cache_time:
            _log.info("Cached data expired")
            raise CacheExpiredError()
    except OSError as err:
        _log.warning(str(err))
        raise CacheExpiredError() from err

    return json.load(open(filename))

def cache_data(data):
    filename = _get_cache_file_name()
    _log.info("Caching data to %s" % filename)
    fp = open(filename, "w")
    json.dump(data, fp)
