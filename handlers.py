"""Handle events dynamically.

Want to be able to reload event handlers as needed
"""

import logging
import irc.modes
import threading
import time

from command import Command, CommandHandler
from abuse import ml, heuristics

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


class Lockdown(Handler):
    """Manage lockdowns."""

    can_moderate = ['#miraheze', '#miraheze-cvt']

    def __init__(self, bot):
        """Lockdown handler."""
        super().__init__(bot)
        self.locked_down = bot.saves.setdefault('locked_down', [])
        self.pending = {}
        self.pending_users = {}
        self.auto = bot.saves.setdefault('lock_auto', False)
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
        self.auto = bot.saves['lock_auto'] = not old
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
            if user in [connection.get_nickname(), 'ChanServ']:
                continue
            if chan not in self.pending_users:
                self.pending_users[chan] = []
            self.pending_users[chan].append(user)
            connection.userhost([user])

    def on_userhost(self, connection, event):
        """Grant ops to trusted users."""
        user = event.arguments[0].split('=')[0].strip(' *')
        host = event.arguments[0].split('@')[-1].strip()
        for chan in self.pending_users:
            if user in self.pending_users[chan]:
                if chan in self.bot.trusted.get('op', {}).get(host, []):
                    connection.mode(chan, '+o ' + user)

    def on_join(self, connection, event):
        """Grant ops to trusted users when they join."""
        if event.target in self.locked_down:
            if event.source == connection.get_nickname():
                connection.privmsg('ChanServ', f'OP {event.target} {connection.get_nickname()}')
            if event.target in self.bot.trusted.get('op', {}).get(event.source.host, []):
                connection.mode(event.target, '+o ' + event.source.nick)

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


class MLHandler(Handler):
    """Implement machine learning abuse detection."""

    def __init__(self, bot):
        """Initialize needed stuff."""
        super().__init__(bot)
        self.pending_bans = {}
        # Store values in bot to avoid retraining every reload
        self.vectorizer = getattr(bot, 'vectorizer', False)
        self.classifier = getattr(bot, 'classifier', False)
        self.classifier2 = getattr(bot, 'classifier2', False)
        self.heuristics = heuristics.load_rules()
        self.timestamps = {}
        self.mutex = threading.RLock()
        self.commands.append(Command(
            'train',
            self.train,
            restriction=Command.DEVELOPER,
            help="(Re)train dataset (if you don't know what this means, don't touch it!)"
        ))
        if not (self.vectorizer and self.classifier and self.classifier2):
            t_thread = threading.Thread(target=self.train)
            t_thread.start()

    def train(self, *args):
        """Load in vectorizer and classifier."""
        vectorizer, classifier, classifier2 = ml.train(self.bot.path / 'abuse/dataset.csv')
        # Store values in bot to avoid retraining every reload
        self.bot.vectorizer = self.vectorizer = vectorizer
        self.bot.classifier = self.classifier = classifier
        self.bot.classifier2 = self.classifier2 = classifier2

    def check_flood(self, nick):
        """Attempt to determine if supplied nick is flooding."""
        # TODO: replace with better whitelist (incorporate into heuristics points?)
        with self.mutex:
            if "Bot" in nick or "Not" in nick:
                return False
            if nick not in self.timestamps:
                self.timestamps[nick] = [time.time()]
                return False
            now = time.time()
            timestamps = self.timestamps[nick]
            for timestamp in timestamps.copy():
                if now - timestamp > 30:
                    # Ignore all timestamps older than 30s
                    timestamps.remove(timestamp)
            total = len(timestamps)
            if total < 4:
                self.timestamps[nick].append(now)
                return False
            if total > 30:
                self.timestamps.pop(nick)  # Don't trip repeatedly on the same user
                return True  # Hard limit at 1msg/sec over 30s
            avg = (now - timestamps[0]) / (total + 1)  # A simpler system, 0 index should be oldest
            if -(2.4 / total) + 3 > avg:
                self.timestamps.pop(nick)  # Don't trip repeatedly on the same user
                return True  # I don't want to explain this math, so I hope it works
            self.timestamps[nick].append(now)
            return False

    def _clean(self):
        """Clear old entries from timestamps."""
        with self.mutex:
            now = time.time()
            nicks = list(self.timestamps.keys())
            for nick in nicks:
                for timestamp in self.timestamps[nick].copy():
                    if now - timestamp > 30:
                        self.timestamps[nick].remove(timestamp)
                if len(self.timestamps[nick]) == 0:
                    self.timestamps.pop(nick)

    def on_pubmsg(self, connection, event):
        """Process public messages for abuse."""
        if not(self.vectorizer and self.classifier):
            return
        words = ' '.join(event.arguments)
        wordbag = self.vectorizer.transform([words])
        c = event.target

        # Flood detection
        if self.check_flood(event.source.nick):
            log.warn(f'Detected flooding from "{event.source.nick}" in {c}')

        # Classifier1
        if self.classifier.predict(wordbag).tolist()[0]:
            """Not ready for use
            for rule in self.heuristics:
                if rule.apply(event) <= -1000:
                    return  # Whitelist users
            """
            log.warn(f'Classifier1 detected abusive message: "{words}" from "{event.source}" in "{c}"')
            """Not ready for use
            channel = self.bot.channels[c]
            if channel.is_oper(connection.get_nickname):
                connection.mode(c, '+b ' + event.sender.host)
                connection.kick(c, event.sender.nick)
            else:
                if c not in self.pending_bans:
                    self.pending_bans[c] = []
                self.pending_bans[c].append(event.sender)
                connection.privmsg('ChanServ', f'OP {c} {connection.get_nickname()}')
            """

        # Classifier2
        points = self.classifier2.predict_proba(wordbag).tolist()[0][1]
        points = int(points * 100)
        for rule in self.heuristics:
            points += rule.apply(event)
        if points >= 95 or self.classifier2.predict(wordbag).tolist()[0]:
            log.warn(f'Classifier2 tripped with score {points} on: "{words}" from "{event.source}" in "{c}"')

        self._clean()  # Housekeeping

    def on_mode(self, connection, event):
        """Process pending bans."""
        if event.target in self.pending_bans:
            modes = irc.modes.parse_channel_modes(' '.join(event.arguments))
            for mode in modes:
                if mode == ['+', 'o', connection.get_nickname()]:
                    for user in self.pending_bans[event.target]:
                        connection.mode(event.target, '+b ' + user.host)
                        connection.kick(event.target, user.nick)
                    self.pending_bans.pop(event.target)


class AuthPageHandler(Handler):
    """Automagically reset Discord/auth after detecting edits."""

    def __init__(self, bot):
        """Setup that probably can just be skipped, but w/e."""
        super().__init__(bot)

    def on_pubmsg(self, connection, event):
        """Process incoming messages."""
        if event.target == "#miraheze-feed" and "metawiki * [[Discord/auth]]" in ' '.join(event.arguments)):
            with open(self.bot.path / "Discord.auth.txt") as file:
                content = file.read()
                self.bot.apis['meta'].edit('Discord/auth', content, "BOT: resetting page")


def load_handlers(bot):
    """Return an array of all in use handlers."""
    handlers = []
    handlers.append(Lockdown(bot))
    handlers.append(MLHandler(bot))
    handlers.append(AuthPageHander(bot))
    for handler in handlers:
        handler.load_commands()
    return handlers
