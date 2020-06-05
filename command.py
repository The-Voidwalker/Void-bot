"""Handles commands.

Do not use without Void's permission
"""


class Command:
    """A class representing a command.

    This is not the command we receive from IRC
    """

    GENERAL = 0
    VOICED = 1
    OPERATOR = 2
    TRUSTED = 3
    DEVELOPER = 4

    def __init__(self, name, action, prefix='$', restriction=0, enabled=True, help=False):
        """Create a command object."""
        self.name = name
        self.action = action
        self.prefix = prefix
        self.restriction = restriction
        self.enabled = True
        self.help = help

    def allowed(self, trust_level):
        """Determine if the supplied trust level is sufficient to run the command.

        Also, don't run the command if it was disabled.
        """
        return self.enabled and self.restriction <= trust_level


class CommandHandler:
    """A class that handles commands from IRC."""

    commands = []
    master_commands = []
    trusted = []

    def __init__(self, event, bot):
        """Create a command handler."""
        self.event = event
        self.sender = event.source
        self.line = event.arguments[0]
        self.bot = bot

    def find_command(self):
        """Identify the command in the line.

        Returns a command object if a command can be found, otherwise False.
        """
        prefix = self.line[:1]
        word = self.line.split()[0][1:]
        for command in (self.master_commands + self.commands):
            if command.prefix == prefix and command.name == word:
                return command
        return False

    def perm_level(self):
        """Determine the permission level of the sender."""
        if self.sender.host == 'wikipedia/The-Voidwalker':
            return Command.DEVELOPER
        if self.sender.host in self.trusted:
            return Command.TRUSTED
        if self.event.target[0] == '#':
            channel = self.bot.channels[self.event.target]
            if channel.is_oper(self.sender.nick):
                return Command.OPERATOR
            if channel.is_voiced(self.sender.nick):
                return Command.VOICED
        return Command.GENERAL

    def run(self):
        """Run the command handler."""
        command = self.find_command()
        if command is not False and command.allowed(self.perm_level()):
            command.action(self.bot, self.event)

    @classmethod
    def enable_command(cls, command_name):
        """Enable the supplied command.

        Returns true if command was found, false otherwise.
        """
        for command in cls.commands:
            if command.name == command_name:
                command.enabled = True
                return True
        return False

    @classmethod
    def disable_command(cls, command_name):
        """Disable the supplied command.

        Returns true if command was found, false otherwise.
        """
        for command in cls.commands:
            if command.name == command_name:
                command.enabled = False
                return True
        return False

    @classmethod
    def get_command(cls, name):
        """Find a command matching the :name: parameter."""
        for command in (cls.master_commands + cls.commands):
            if command.name == name:
                return command
        return False

    @classmethod
    def clear_commands(cls):
        """Clear all commands known by the command handler."""
        cls.master_commands.clear()
        cls.commands.clear()
