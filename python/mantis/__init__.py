import click
from mantis.consume import consume
from mantis.load_gen import load_gen
from mantis.metric import metric_monitor, result_writer


@click.group()
def cli():
    pass


cli.add_command(consume)
cli.add_command(load_gen)
cli.add_command(metric_monitor)
cli.add_command(result_writer)


def wrapper():
    cli(standalone_mode=False)

