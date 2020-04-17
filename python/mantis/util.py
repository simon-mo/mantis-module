from structlog import get_logger

logger = get_logger()


def parse_custom_args(custom_args):
    init_args = dict()
    for k, v in map(lambda s: s.split("="), custom_args.split(",")):
        init_args[k] = v
    logger.msg(f"Custom arguments are not None. The parsed result is {init_args}")
    return init_args
