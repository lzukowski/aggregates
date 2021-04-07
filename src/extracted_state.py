from project_management import Command, Handler


class CommandHandler(Handler):
    def __call__(self, cmd: Command) -> None:
        raise NotImplementedError
