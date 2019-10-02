"""An IRC Bot that handles too much.

This is intended for internal use only
Do not use this file outside of Void's permission.
"""

import commands
import irc.modes
import logging

from importlib import reload
from irc.bot import SingleServerIRCBot, ServerSpec
from wiki.api import Api

log = logging.getLogger(__name__)


class VoidBot(SingleServerIRCBot):
    """The setup for VoidBot, requires a lot of stuff.

    TODO: Docs
    """

    def __init__(self, password):
        """Create a VoidBot."""
        super().__init__([ServerSpec('irc.freenode.net')], 'Void-bot', 'VoidBot')
        self.account = 'Void|Bot'
        self.dev = 'wikipedia/The-Voidwalker'
        self.__password = password
        self.channel_list = []
        self.discord = False
        self.apis = {
            'meta': Api('miraheze', 'meta.miraheze.org'),
            'cvt': Api('miraheze', 'cvt.miraheze.org'),
            'testadminwiki': Api('testadminwiki', 'testwiki.wiki', script_path='')
        }
        self.probably_connected = True
        self.reactor.scheduler.execute_every(600, self.check_connection)

    def _identify(self):
        """Login with NickServ."""
        self.connection.privmsg('NickServ', f'IDENTIFY {self.account} {self.__password}')

    def check_connection(self):
        """Verify connection to server."""
        self.probably_connected = False
        self.reactor.scheduler.execute_after(30, self.check_connection_call)
        self.connection.ping('freenode.net')

    def check_connection_call(self):
        """Handle possible disconnect."""
        if not self.probably_connected:
            log.info('Bot is probably disconnected')
            self.connection.disconnect(message="I'm probably no longer connected to the server. Oops!")

    def on_pong(self, connection, event):
        self.probably_connected = True

    def get_version(self):
        """Return my bot description.

        TODO: Add version counter
        """
        return 'Python irc.bot VoidBot 1'

    def on_welcome(self, connection, event):
        """Handle welcome."""
        self._identify()

    def on_396(self, connection, event):
        """Join channels after cloak is applied."""
        if event.arguments[0] == 'miraheze/bot/Void':
            for channel in self.channel_list:
                connection.join(channel)

    def on_pubmsg(self, connection, event):
        """Search public messages for commands."""
        sender = event.source
        if sender.host == self.dev and event.arguments[0] == '$reload':
            reload(commands)
            connection.privmsg(event.target, 'Reloaded Commands!')
        handler = commands.CommandHandler(event, self)
        handler.run()

    def on_privmsg(self, connection, event):
        """Handle commands in private messages."""
        sender = event.source
        if sender.host == self.dev and event.arguments[0] == '$reload':
            reload(commands)
            connection.privmsg(sender.nick, 'Reloaded Commands!')
        handler = commands.CommandHandler(event, self)
        handler.run()

    def on_join(self, connection, event):
        """Help Zppix with his damn bot."""
        sender = event.source
        channel = event.target
        if channel == '#miraheze-cvt' and sender.host == 'miraheze/bot/Zppix' and sender.nick != 'ZppixBot':
            self.discord = sender.nick
            connection.privmsg('ChanServ', f'OP #miraheze-cvt-private {connection.get_nickname()}')

    def on_mode(self, connection, event):
        """Help Zppix with his damn bot part 2."""
        if self.discord is not False and event.target == '#miraheze-cvt-private':
            modes = irc.modes.parse_channel_modes(event.arguments[0])
            for mode in modes:
                if mode == ['+', 'o', None]:
                    connection.invite(self.discord, '#miraheze-cvt-private')
                    connection.mode(event.target, '-o '+connection.get_nickname())
                    self.discord = False
                    break
