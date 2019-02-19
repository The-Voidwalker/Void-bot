"""Helper classes.

Some are specific to VoidBot
"""

from datetime import datetime


class Logger:
    """A class representing a wiki logger."""

    def __init__(self, api, page, header, source, log):
        """Init logger.

        :param api: (Api) Api object for the wiki
        :param page: (string) Title of log page
        :param header: (string) Header the log entries go under
        :param log: (string) Log entry
        """
        self.api = api
        self.page = page
        self.header = header
        self.source = source
        self.log = log

    def run(self):
        """Perform logging operation."""
        page_text = self.api.page(self.page)
        try:
            header_index = page_text.index(self.header) + len(self.header)
            page_text = page_text[:header_index] + f'\n{self.log}' \
                + page_text[header_index:]
        except ValueError:
            page_text = f'{self.header}\n{self.log}\n' + page_text
        self.api.edit(self.page, page_text, f'Logging item from {self.source}')

    @staticmethod
    def irc_entry(event, format):
        """Parse an event from IRC into a log entry.

        :param format: (string) Format of log entry
        Must be in the same format as datetime strformat
        where %s is the source, and %L is the log.
        """
        source = event.source.nick
        log = event.arguments[0][5:]  # Get rid of "%log"
        now = datetime.utcnow()
        format = format.replace('%s', source).replace('%L', log)
        return now.strftime(format)


class FarmerPatrol:
    """A class to patrol the farmer log."""

    def __init__(self, api):
        """Init FarmerPatrol.

        :param api: (Api) Api object for wiki
        """
        self.api = api
