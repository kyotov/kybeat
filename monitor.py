#!/Users/kamen/PycharmProjects/kybeat/venv/bin/python

import logging

import click

from kybeat_server import KyBeatServer


@click.command()
@click.option("--behavior", type=click.Choice(["good", "distracted", "bad"]), default="good")
def main(behavior: str):
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s : %(process)d (server:%(name)s) : [%(levelname)s] %(message)s")
    KyBeatServer(f"./child.py --behavior={behavior}")


if __name__ == "__main__":
    main()
