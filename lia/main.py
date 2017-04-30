import logging, sys, os, argparse, inspect

def get_logger():
    valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    try:
        env_level = os.environ["LOG_LEVEL"]
        valid_levels.remove(env_level)
        level = getattr(logging, env_level)
    except KeyError:
        level = logging.WARNING
    except ValueError:
        msg = "Expected log level: %s, got: %s. Using default level WARNING." \
                % ("|".join(valid_levels), env_level)
        print(msg, file = sys.stderr)
        level = logging.WARNING

    logging.basicConfig(level = level)
    return logging.getLogger(__name__)

def main():
    log = get_logger()

    ap = argparse.ArgumentParser(description = "LDAP Inventory for Ansible")
    group = ap.add_mutually_exclusive_group(required = True)
    group.add_argument("--list",
            action = "store_true",
            help = "Print all groups and vars")
    group.add_argument("--host",
            help = "Print vars for a host")

    ap.parse_args()

if __name__ == "__main__":
    main()
