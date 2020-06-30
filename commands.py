"""Defines commands.

Do not use without Void's permission
"""

import logging
import sys
from datetime import datetime
from wiki.api import ApiError, ConnectionError
from wiki.helpers import Logger
from command import Command, CommandHandler

logs = logging.getLogger(__name__)


def kill(bot, event):
    """Shutdown bot instance."""
    sender = event.source.nick
    bot.connection.disconnect(f'{sender} has brought the end upon us!')  # TODO cycle quit messages
    logs.warning(f'{sender} has killed the bot')
    sys.exit(0)


help_str = 'End the bot. (Requires Trusted)'
CommandHandler.master_commands.append(Command('kill', kill, restriction=Command.TRUSTED, help=help_str))


def cmd_disable(bot, event):
    """Disable a command."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    args = event.arguments[0].split()[1:]
    if len(args) == 0:
        return bot.connection.privmsg(target, "I can't disable what you don't tell me about.")
    if not CommandHandler.disable_command(args[0]):
        return bot.connection.privmsg(target, f'I can\'t disable what does not exist! (Could not find "{args[0]}")')
    else:
        logs.info(f'{event.source.nick} has disabled command {args[0]}')


help_str = 'Attempt to disable the supplied command. Core commands cannot be disabled. (Requires Trusted)'
CommandHandler.master_commands.append(Command('disable', cmd_disable, restriction=Command.TRUSTED, help=help_str))


def cmd_enable(bot, event):
    """Enable a command."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    args = event.arguments[0].split()[1:]
    if len(args) == 0:
        return bot.connection.privmsg(target, "I can't enable what you don't tell me about.")
    if not CommandHandler.enable_command(args[0]):
        return bot.connection.privmsg(target, f'I can\'t enable what does not exist! (Could not find "{args[0]}")')
    else:
        logs.info(f'{event.source.nick} has enabled command {args[0]}')


help_str = 'Attempt to enable the supplied command. (Requires Trusted)'
CommandHandler.master_commands.append(Command('enable', cmd_enable, restriction=Command.TRUSTED, help=help_str))


def nick(bot, event):
    """Change the bot's nick."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    args = event.arguments[0].split()[1:]
    if len(args) == 0:
        return bot.connection.privmsg(target, "That's not a nick! That's nothing!")
    bot.connection.nick(args[0])
    logs.info(f'{event.source.nick} has changed our nick to {args[0]}')


help_str = 'Change the nick of the bot to the supplied value. (Requires Trusted)'
CommandHandler.commands.append(Command('nick', nick, restriction=Command.TRUSTED, help=help_str))


def join(bot, event):
    """Join channels."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    args = event.arguments[0].split()[1:]
    if len(args) == 0:
        return bot.connection.privmsg(target, "I can't join if you don't tell me the channel name!")
    if args[0][0] != '#':
        return bot.connection.privmsg(target, f'"{args[0]}" is not a channel!')
    bot.connection.join(args[0])
    logs.info(f'{event.source.nick} has asked us to join {args[0]}')


help_str = 'Join the supplied channel. (Requires Trusted)'
CommandHandler.commands.append(Command('join', join, restriction=Command.TRUSTED, help=help_str))


def part(bot, event):
    """Part channels."""
    if event.type == 'privmsg':
        return bot.connection.privmsg(event.source.nick, 'This command can only be used from a channel!')
    channel = event.target
    sender = event.source.nick
    if channel == '##voidwalker':
        return bot.connection.privmsg(channel, 'I cannot leave this channel. Voidwalker hath forbidden it.')
    bot.connection.privmsg(channel, f'Goodbye {channel}!')
    bot.connection.part(channel, message=f':{sender} has sent me to a far off land!')
    logs.info(f'{sender} has caused us to part from {channel}')


help_str = 'Part the current channel. (Requires ChanOp)'
CommandHandler.commands.append(Command('part', part, restriction=Command.OPERATOR, help=help_str))


def partf(bot, event):
    """Part from channels."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    sender = event.source.nick
    args = event.arguments[0].split()[1:]
    if len(args) == 0:
        return bot.connection.privmsg(target, 'This command only works if you tell me what channel to leave.')
    if args[0][0] != '#':
        return bot.connection.privmsg(target, f'"{args[0]}" is not a channel!')
    if args[0] == '##voidwalker':
        return bot.connection.privmsg(target, "I am forbidden from leaving my master's realm.")
    bot.connection.part(args[0], message=f':{sender} has sent me to a far off land!')
    logs.info(f'{sender} has removed us from {args[0]}')


help_str = 'Part the supplied channel. (Requires Trusted)'
CommandHandler.commands.append(Command('partf', partf, restriction=Command.TRUSTED, help=help_str))


def help(bot, event):
    """Find help strings."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    args = event.arguments[0].split()[1:]
    if len(args) == 0:
        return bot.connection.privmsg(target, 'Please see https://meta.miraheze.org/wiki/User:Void-bot/Help')
    command = CommandHandler.get_command(args[0])
    if command is False or command.help is False:
        return bot.connection.privmsg(target, f'Sorry, I could not find help on {args[0]}.')
    bot.connection.privmsg(target, command.help)


help_str = 'Provides general help, or help on a supplied command.'
CommandHandler.commands.append(Command('help', help, restriction=Command.GENERAL, help=help_str))


def access(bot, event):
    """Report user's access levels."""
    target = event.target if event.type == 'pubmsg' else event.source.nick
    sender = event.source.nick
    dummy = CommandHandler(event, bot)
    access_level = dummy.perm_level()
    bot.connection.privmsg(target, f'{sender} has level {access_level} clearance.')


help_str = 'Tells you what kind of access you have.'
CommandHandler.commands.append(Command('access', access, restriction=Command.GENERAL, help=help_str))


def log(bot, event):
    """Perform logging."""
    if event.target == '#miraheze-cvt':
        api = bot.apis['cvt']
        page = 'CVT action log'
        header = '== Log =='
        source = event.source.nick
        format = '* <%s> %L --~~~~~'
        try:
            log_entry = Logger.irc_entry(event, format)
            Logger(api, page, header, source, log_entry).run()
            bot.connection.privmsg(event.target, f'Saved item "{event.arguments[0][5:]}"')
            logs.info(f'{source} issued cvt log; {event.arguments[0][5:]}')
        except (ConnectionError, ApiError) as e:
            bot.connection.privmsg(event.target, 'Failed to save item!')
            logs.exception(e)
    elif event.target == '#testadminwiki':
        api = bot.apis['testadminwiki']
        page = 'Test Wiki: Server admin log'
        now = datetime.utcnow()
        header = now.strftime('== %Y-%m-%d ==')
        source = event.source.nick
        format = '* %H:%M %s: %L'
        try:
            log_entry = Logger.irc_entry(event, format)
            Logger(api, page, header, source, log_entry).run()
            bot.connection.privmsg(event.target, f'Saved item "{event.arguments[0][5:]}"')
            logs.info(f'{source} issued sal log; {event.arguments[0][5:]}')
        except (ConnectionError, ApiError) as e:
            bot.connection.privmsg(event.target, 'Failed to save item!')
            logs.exception(e)
    elif event.target == '#miraheze-bots':
        api = bot.apis['botwiki']
        page = 'MirahezeBotsWiki:Server admin log'
        now = datetime.utcnow()
        header = now.strftime('== %Y-%m-%d ==')
        source = event.source.nick
        format = '* <%s> %L --~~~~'
        try:
            log_entry = Logger.irc_entry(event, format)
            Logger(api, page, header, source, log_entry).run()
            bot.connection.privmsg(event.target, f'Saved item "{event.arguments[0][5:]}"')
            logs.info(f'{source} issued botwiki SAL; {event.arguments[0][5:]}')
        except (ConnectionError, ApiError) as e:
            bot.connection.privmsg(event.target, 'Failed to save item!')
            logs.exception(e)


help_str = 'Does cvt log and testadminwiki server admin log.'
CommandHandler.commands.append(Command('log', log, restriction=Command.VOICED, help=help_str))


def ping(bot, event):
    """Check connection."""
    if event.target == '##voidwalker':
        bot.check_connection()


help_str = "Debug only. Please don't play with this!"
CommandHandler.commands.append(Command('ping', ping, restriction=Command.DEVELOPER, help=help_str))
