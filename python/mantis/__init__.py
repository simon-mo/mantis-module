import click
from mantis.consume import consume
from mantis.load_gen import load_gen


@click.group()
def cli():
    pass


cli.add_command(consume)
cli.add_command(load_gen)


def wrapper():
    cli(standalone_mode=False)
