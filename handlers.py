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

    def _ignore(self, *args):
        pass

    def run(self, connection, event):
        """Run on events we have methods for."""
        if event.type not in self.skip_events:
            getattr(self, f'on_{event.type}', self._ignore)(connection, event)


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
            connection.userhost(user)

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
        modes = irc.modes.parse_channel_modes(event.arguments[0])
        for mode in modes:
            if event.target not in self.locked_down:
                if mode == ['+', 'q', '*!*@*']:  # and channel.has_mode('z'):  # may not be +z yet
                    self.pre_lockdown(connection, event.target)
                    break
            else:
                if mode == ['-', 'q', '*!*@*']:  # and channel.has_mode('z'):  # z may be dropped first (handle that?)
                    self.pre_unlock(connection, event.target)
                    break


def test_uhost(bot, event):
    """Test only, please remove."""
    bot.connection.send_items('USERHOST', 'Voidwalker')


CommandHandler.commands.append(Command('uhost', test_uhost, restriction=Command.DEVELOPER, help='Testing only'))


def load_handlers(bot):
    """Return an array of all in use handlers."""
    handlers = []
    handlers.append(BotHelper(bot))
    handlers.append(Lockdown(bot))
    return handlers
