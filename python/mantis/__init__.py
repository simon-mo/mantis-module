import click
from mantis.consume import consume
from mantis.load_gen import load_gen
from mantis.runner import run_controller


@click.group()
def cli():
    pass


cli.add_command(consume)
cli.add_command(load_gen)
cli.add_command(run_controller)


def wrapper():
    cli(standalone_mode=False)
