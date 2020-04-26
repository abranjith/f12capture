import click

def echo_success(message):
    click.secho(f"SUCCESS : {message}", fg="bright_green")

def echo_warning(message):
    click.secho(f"WARNING : {message}", fg="bright_yellow")

def echo_error(message, raise_=False):
    if raise_:
        styled_message = click.style(message, fg="bright_red")
        raise click.ClickException(styled_message)
    click.secho(f"ERROR : {message}", fg="bright_red", blink=True)