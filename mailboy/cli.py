"""Console script for mailboy."""
import sys
import click

from mailboy import mailboy


@click.command()
@click.option('--mode', type=click.Choice(['single', 'poll', 'idle']),
              default='single', help='Specify run mode')
@click.option('--poll-interval', default=10, help='Sleep interval when running in IMAP poll mode.')
@click.option('--workdir', default='.', help='Directory containing "conf" and "log" directory')
@click.option('--logdir', default='./log', help='Path to "log" directory.')
@click.option('--confdir', default='./conf', help='Path to "conf" directory.')
def main(mode, poll_interval, workdir, logdir, confdir):
    """Console script for mailboy."""
    mailboy.run(mode, poll_interval)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
