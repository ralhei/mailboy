"""Console script for mailboy."""
import sys
import pathlib
import logging.config

import click
import easyconfig

from mailboy import mailboy


@click.command()
@click.option('--mode', type=click.Choice(['single', 'poll', 'idle']),
              default='single', help='Specify run mode')
@click.option('--poll-interval', default=10, help='Sleep interval when running in IMAP poll mode.')
@click.option('--workdir', default='.', help='Directory containing "conf" and "log" directory')
@click.option('--logdir', default='./log', help='Path to "log" directory.')
@click.option('--confdir', default='./config', help='Path to "conf" directory.')
def main(mode, poll_interval, workdir, logdir, confdir):
    """Console script for mailboy."""
    log_conf = pathlib.Path(confdir, 'logging.conf')
    mailboy_conf = pathlib.Path(confdir, 'mailboy.conf')
    if not log_conf.exists():
        sys.stderr.write(f'Cannot find {log_conf}\n')
        sys.exit(1)
    if not mailboy_conf.exists():
        sys.stderr.write(f'Cannot find {mailboy_conf}\n')
        sys.exit(1)
    logging.config.fileConfig(log_conf)
    config = easyconfig.EasyConfigParser()
    config.read(mailboy_conf)
    mailboy.run(config.ns, mode, poll_interval)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
