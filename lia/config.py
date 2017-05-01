import logging, os, json

_cfg = None

class MissingConfigValue(Exception):
    pass

def get_config():
    global _cfg

    if not _cfg:
        _cfg = Config()

    return _cfg

class Config:
    def __init__(self, attrs = None):
        if attrs:
            self._attrs = attrs
        else:
            self._attrs = self._load()

    def _load(self):
        basename = "lia.json"
        try:
            filename = os.path.join(os.environ["XDG_CONFIG_HOME"], basename)
        except KeyError:
            filename = os.path.join(os.environ["HOME"], ".config", basename)

        logging.getLogger(__name__).debug("Loading config from %s" % filename)

        return json.load(open(filename))

    def __getattr__(self, name):
        try:
            attr = self._attrs[name]
            if type(attr) is dict:
                return __class__(attr)
            else:
                return attr

        except KeyError as err:
            msg = "Value '%s' is missing in config" % name
            raise MissingConfigValue(msg) from err
