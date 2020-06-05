"""Handle events dynamically.

Want to be able to reload event handlers as needed
"""

import logging
import irc.modes

from command import Command, CommandHandler

log = logging.getLogger(__name__)


class Handler():
    """Abstract Handler."""

    def __init__(self, bot):
        """Create a handler for events."""
        self.bot = bot
        self.skip_events = []
        self.commands = []

    def _ignore(self, *args):
        pass

    def run(self, connection, event):
        """Run on events we have methods for."""
        if event.type not in self.skip_events:
            getattr(self, f'on_{event.type}', self._ignore)(connection, event)

    def load_commands(self):
        """Load in registered commands."""
        for command in self.commands:
            CommandHandler.commands.append(command)


class BotHelper(Handler):
    """Help MH-Discord join a private channel."""

    def __init__(self, bot):
        """Create bot helper handler."""
        super().__init__(bot)
        self.discord = False
        self.skip_events.append('mode')

    def on_join(self, connection, event):
        """Help Zppix with his damn bot."""
        sender = event.source
        channel = event.target
        if channel == '#miraheze-cvt' and sender.host == 'miraheze/bot/Zppix' and sender.nick != 'ZppixBot':
            self.discord = sender.nick
            self.skip_events.remove('mode')
            connection.privmsg('ChanServ', f'OP #miraheze-cvt-private {connection.get_nickname()}')

    def on_mode(self, connection, event):
        """Help Zppix with his damn bot part 2."""
        if self.discord is not False and event.target == '#miraheze-cvt-private':
            modes = irc.modes.parse_channel_modes(' '.join(event.arguments))
            for mode in modes:
                if mode == ['+', 'o', connection.get_nickname()]:
                    self.skip_events.append('mode')
                    connection.invite(self.discord, '#miraheze-cvt-private')
                    connection.mode(event.target, '-o ' + connection.get_nickname())
                    self.discord = False
                    break


class Lockdown(Handler):
    """Manage lockdowns."""

    can_moderate = ['#miraheze', '#miraheze-cvt']

    def __init__(self, bot):
        """Lockdown handler."""
        super().__init__(bot)
        self.locked_down = []
        self.pending = {}
        self.pending_users = {}
        # self.get_locked_down()  # In case of bot restarts, needs update
        self.auto = False
        self.commands.append(Command(
            'lockdown',
            self.lockdown_cmd,
            restriction=Command.DEVELOPER,
            help='Manage lockdowns. Command format is $lockdown <enable|lift> [channel]'
        ))
        self.commands.append(Command(
            'toggleauto',
            self.toggle_auto,
            restriction=Command.DEVELOPER,
            help='Toggle automatic handling of lockdowns.'
        ))

    def toggle_auto(self, bot, event):
        """Toggle automatic lockdown detection."""
        target = event.target if event.type == 'pubmsg' else event.source.nick
        old = self.auto
        self.auto = not old
        if old:
            bot.connection.privmsg(target, 'Automatic handling of lockdowns was disabled.')
        else:
            bot.connection.privmsg(target, 'Automatic handling of lockdowns was enabled.')

    def lockdown_cmd(self, bot, event):
        """Lockdown command."""
        target = event.target if event.type == 'pubmsg' else event.source.nick
        args = event.arguments[0].split()[1:]
        if len(args) == 0:
            bot.connection.privmsg(target, 'Command format is $lockdown <enable|lift> [channel]')
        elif len(args) == 1:
            if not event.type == 'pubmsg':
                bot.connection.privmsg(target, 'A target channel is required if using private messages!')
            elif args[0] in ['enable', 'lift']:
                if target not in self.can_moderate:
                    bot.connection.privmsg(target, 'Cannot moderate this channel!')
                elif args[0] == 'enable':
                    self.pre_lockdown(bot.connection, target)
                elif args[0] == 'lift':
                    self.pre_unlock(bot.connection, target)
            else:
                bot.connection.privmsg(target, f'Unrecognised option "{args[0]}"')
        else:
            if args[0] in ['enable', 'lift']:
                if args[1][0] != '#':
                    bot.connection.privmsg(target, f'"{args[1]}" is not a channel!')
                elif args[1] not in self.can_moderate:
                    bot.connection.privmsg(target, f'Cannot moderate "{args[1]}"!')
                elif args[0] == 'enable':
                    self.pre_lockdown(bot.connection, args[1])
                elif args[0] == 'lift':
                    self.pre_unlock(bot.connection, args[1])
                else:
                    bot.connection.privmsg(target, 'Something went wrong :(')
            else:
                bot.connection.privmsg(target, f'Unrecognised option "{args[0]}"')

    def pre_lockdown(self, connection, channel):
        """Pre lockdown checks."""
        if channel not in self.bot.channels:
            log.warn(f'Bot not in expected channel "{channel}"')
            return
        if self.bot.channels[channel].is_oper(connection.get_nickname()):
            self.do_lockdown(connection, channel)
        else:
            self.pending[channel] = self.do_lockdown
            connection.privmsg('ChanServ', f'OP {channel} {connection.get_nickname()}')

    def do_lockdown(self, connection, chan):
        """Do lockdown procedure."""
        if chan not in self.locked_down:
            self.locked_down.append(chan)
        else:
            log.warn(f'Enabling lockdown in {chan} despite channel appearing locked down?')
        channel = self.bot.channels[chan]
        connection.mode(chan, '+qz *!*@*')
        for user in channel.users():
            if chan not in self.pending_users:
                self.pending_users[chan] = []
            self.pending_users[chan].append(user)
            connection.userhost([user])

    def on_userhost(self, connection, event):
        """Grant ops to trusted users."""
        for chan in self.pending_users:
            pass
            # TODO: I don't actually know what this event looks like

    def pre_unlock(self, connection, channel):
        """Pre unlock checks."""
        if channel not in self.bot.channels:
            log.warn(f'Bot not in expected channel "{channel}"')
            return
        if self.bot.channels[channel].is_oper(connection.get_nickname()):
            self.drop_lockdown(connection, channel)
        else:
            self.pending[channel] = self.drop_lockdown
            connection.privmsg('ChanServ', f'OP {channel} {connection.get_nickname()}')

    def drop_lockdown(self, connection, chan):
        """Drop lockdown."""
        if chan in self.locked_down:
            self.locked_down.remove(chan)
        else:
            log.warn(f'Removing lockdown from {chan} despite no lockdown in place?')
        # channel = self.bot.channels[chan]
        connection.mode(chan, '-q *!*@*')
        # TODO: DEOP OPS?

    def get_locked_down(self):
        """Identify channels that are locked down at startup/reload."""
        # TODO, figure out a way to update for +q *!*@* instead of +m
        connection = self.bot.connection
        for chan in self.can_moderate:
            try:
                channel = self.bot.channels[chan]
                if channel.is_moderated() and channel.has_mode("z"):
                    self.locked_down.append(chan)
                    connection.privmsg('ChanServ', f'OP {chan} {connection.get_nickname()}')
            except KeyError:
                log.debug(f'Bot is not in expected channel "{chan}"')

    def on_mode(self, connection, event):
        """Handle various mode changes."""
        if event.target in self.pending:
            modes = irc.modes.parse_channel_modes(' '.join(event.arguments))
            for mode in modes:
                # TODO: verify
                if mode == ['+', 'o', connection.get_nickname()]:
                    self.pending[event.target](connection, event.target)
                    self.pending.pop(event.target)
        if self.auto:
            self.on_mode_auto(connection, event)

    def on_mode_auto(self, connection, event):
        """Automatically enable/disable lockdown based on mode changes."""
        if event.target not in self.can_moderate:
            return
        # channel = self.bot.channels[event.target]
        modes = irc.modes.parse_channel_modes(' '.join(event.arguments))
        for mode in modes:
            if event.target not in self.locked_down:
                if mode == ['+', 'q', '*!*@*']:  # and channel.has_mode('z'):  # may not be +z yet
                    self.pre_lockdown(connection, event.target)
                    break
            else:
                if mode == ['-', 'q', '*!*@*']:  # and channel.has_mode('z'):  # z may be dropped first (handle that?)
                    self.pre_unlock(connection, event.target)
                    break


def load_handlers(bot):
    """Return an array of all in use handlers."""
    handlers = []
    handlers.append(BotHelper(bot))
    handlers.append(Lockdown(bot))
    for handler in handlers:
        handler.load_commands()
    return handlers
