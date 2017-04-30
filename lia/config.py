import logging, os, json

_cfg = None

def get_config():
    if not _cfg:
        global _cfg = Config()

    return _cfg

def Config:
    def __init__(self):
        basename = "lia.json"
        try:
            filename = os.path.join(os.environ["XDG_CONFIG_HOME"], basename)
        except KeyError:
            filename = os.path.join(os.environ["HOME"], ".config", basename)

        logging.getLogger(__name__).debug("Loading config from %s" % filename)

        self._attrs = json.load(open(filename))

    def __getattr__(self, name):
        return self._attrs[name]
