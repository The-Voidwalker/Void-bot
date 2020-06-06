"""An IRC Bot that handles too much.

This is intended for internal use only
Do not use this file outside of Void's permission.
"""

import command
import commands
import handlers
import logging
import json

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
        self.saves = {}
        self.trusted = {}
        self.banlist = {}
        self.channel_list = []
        self.load()
        self.apis = {
            'meta': Api('miraheze', 'meta.miraheze.org'),
            'cvt': Api('miraheze', 'cvt.miraheze.org'),
            'testadminwiki': Api('testadminwiki', 'testwiki.wiki', script_path='')
        }
        self.probably_connected = True
        self.reactor.scheduler.execute_every(600, self.check_connection)
        self.reactor.scheduler.execute_every(1200, self.save)
        self.handlers = handlers.load_handlers(self)
        self.reactor.add_global_handler('all_events', self.run_handlers, 10)

    @property
    def acl(self):
        """Return both trusted list and ban list as one object."""
        acl = self.trusted.copy()
        acl['banned'] = self.banlist
        return acl

    def load(self):
        """Load saved information from JSON file."""
        with open('save.json', 'r') as saved:
            self.saves = json.loads(saved.read())
        chans = self.saves.get('channel_list', [])
        for chan in chans:
            if chan not in self.channel_list:
                self.channel_list.append(chan)
        self.load_acl()

    def load_acl(self):
        """Load ACLs."""
        with open('acl/trusted.json', 'r') as trusted:
            self.trusted = json.loads(trusted.read())
        with open('acl/banlist.json', 'r') as banlist:
            self.banlist = json.loads(banlist.read())

    def save(self):
        """Save dynamic information."""
        with open('save.json', 'w') as saved:
            saved.write(json.dumps(self.saves))
        with open('acl/banlist.json', 'w') as banlist:
            banlist.write(json.dumps(self.banlist))

    def _identify(self):
        """Login with NickServ."""
        self.connection.privmsg('NickServ', f'IDENTIFY {self.account} {self.__password}')

    def _reload_stuff(self):
        """Reload internal stuff."""
        command.CommandHandler.clear_commands()
        reload(commands)
        reload(handlers)
        self.handlers = handlers.load_handlers(self)

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

    def run_handlers(self, connection, event):
        """Run all known handlers."""
        for handler in self.handlers:
            handler.run(connection, event)

    def on_disconnect(self, connection, event):
        """Safeguard against shutdowns."""
        self.save()

    def on_pong(self, connection, event):
        """Bot is connected."""
        self.probably_connected = True

    def get_version(self):
        """Return my bot description.

        TODO: Add version counter
        """
        return 'Python irc.bot VoidBot 1'

    def on_welcome(self, connection, event):
        """Handle welcome."""
        self._identify()
        log.info('Bot has connected to IRC')

    def on_396(self, connection, event):
        """Join channels after cloak is applied."""
        if event.arguments[0] == 'miraheze/bot/Void':
            for channel in self.channel_list:
                connection.join(channel)

    def on_pubmsg(self, connection, event):
        """Search public messages for commands."""
        sender = event.source
        if sender.host == self.dev and event.arguments[0] == '$reload':
            self._reload_stuff()
            connection.privmsg(event.target, 'Reloaded Commands!')
        handler = command.CommandHandler(event, self)
        handler.run()

    def on_privmsg(self, connection, event):
        """Handle commands in private messages."""
        sender = event.source
        if sender.host == self.dev and event.arguments[0] == '$reload':
            self._reload_stuff()
            connection.privmsg(sender.nick, 'Reloaded Commands!')
        handler = command.CommandHandler(event, self)
        handler.run()
