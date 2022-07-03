"""A representation of the MediaWiki Api."""

import requests
import wiki.auth_config
DEFAULT_USER_AGENT = 'Void-Bot'
requests.utils.default_user_agent = lambda: DEFAULT_USER_AGENT


class Api:
    """A class giving access to certain MediaWiki Api functions."""

    query = {
        'action': 'query',
        'format': 'json',
        'assert': 'bot'
    }

    def __init__(self, name, hostname, script_path='/w', api_path='/api.php'):
        """Init Api class.

        Only supports wikis using https.
        :param name: (string) Name used to fetch from auth_config
        :param hostname: (string) Hostname of wiki (meta.miraheze.org)
        :param script_path: (string) Script path of wiki (/w)
        :param api_path: (string) location of api.php
        """
        self.name = name
        self.hostname = hostname
        self.script_path = script_path
        self.api_path = api_path
        self.url = f'https://{hostname}{script_path}{api_path}'
        self.oauth = wiki.auth_config.auth[name]

    def handle_resp(self, response):
        """Process server response for validity.

        Raises errors if issues are found in response.
        :return: (JSON) server response as JSON
        """
        if response.status_code != 200:
            raise ConnectionError(
                f'Received HTTP "{response.status_code}"'
                + f' from "{self.hostname}"; expected HTTP 200'
            )
        r_json = response.json()
        if 'error' in r_json:
            raise ApiError(
                f'{r_json["error"]["code"]}: {r_json["error"]["info"]}'
            )
        return r_json

    def do_query(self, query):
        """Perform a query.

        :param query: (dictionary) Params of query
        """
        query.update(self.query)  # All querys must follow default
        return self.handle_resp(requests.get(
            self.url,
            params=query,
            auth=self.oauth
        ))

    def siteinfo(self):
        """Perform query for siteinfo.

        :return: (JSON) Site information.
        """
        query = self.query.copy()
        query.update({'meta': 'siteinfo'})
        resp = requests.get(
            self.url,
            params=query,
            auth=self.oauth
        )
        return self.handle_resp(resp)['query']

    def get_token(self, type='csrf'):
        """Fetch a token.

        :param type: (string) Type of token to fetch
        :return: (string) token
        """
        query = self.query.copy()
        query.update({'meta': 'tokens', 'type': type})
        resp = requests.get(
            self.url,
            params=query,
            auth=self.oauth
        )
        return self.handle_resp(resp)['query']['tokens'][f'{type}token']

    def edit(self, page, content, reason, minor=False, bot=True):
        """Edit a page.

        :param page: (string) Name of page to be edited
        :param content: (string) New page contents
        :param reason: (string) Summary of changes
        :param minor: (boolean) Mark changes as minor
        :param bot: (boolean) Mark changes as bot
        """
        token = self.get_token()
        query = self.query.copy()
        query.update({
            'action': 'edit',
            'title': page,
            'text': content,
            'summary': reason,
            'token': token
        })
        if minor:
            query['minor'] = minor
        if bot:
            query['bot'] = bot
        resp = requests.post(
            self.url,
            data=query,
            auth=self.oauth
        )
        self.handle_resp(resp)  # Look for errors

    def page(self, page):
        """Get the contents of a page.

        :param page: (string) Title of page to fetch
        :return: (string) Contents of page
        """
        query = self.query.copy()
        query.update({
            'prop': 'revisions',
            'titles': page,
            'rvprop': 'content',
            'rvslots': 'main'
        })
        resp = requests.get(
            self.url,
            params=query,
            auth=self.oauth
        )
        resp = self.handle_resp(resp)
        pages = resp['query']['pages']
        page_id = list(pages.keys())[0]
        return pages[page_id]['revisions'][0]['slots']['main']['*']

    def block(self, username, reason, expiry='never', anon_only=True,
              no_create=True, auto_block=True, no_email=False,
              allow_user_talk=True, re_block=False):
        """Block a user.

        :param username: (string) Username of user to block
        :param reason: (string) Reason for block
        :param expiry: (string) Expiry time of block
        :param anon_only: (boolean) Apply block to anon users only
        :param no_create: (booelan) Prevent account creation
        :param auto_block: (boolean) Automatically block account ip
        :param no_email: (boolean) Prevent user from sending email
        :param allow_user_talk: (boolean) Allow user to edit own talk
        :param re_block: (boolean) Apply block over existing one
        """
        token = self.get_token()
        query = self.query.copy()
        query.update({
            'action': 'block',
            'user': username,
            'reason': reason,
            'expiry': expiry,
            'anononly': anon_only,
            'nocreate': no_create,
            'autoblock': auto_block,
            'noemail': no_email,
            'allowusertalk': allow_user_talk,
            'reblock': re_block,
            'token': token
        })
        resp = requests.post(
            self.url,
            params=query,
            auth=self.oauth
        )
        self.handle_resp(resp)  # Check for errors

    def global_block(self, target, reason, expiry='never', anononly=True,
                     modify=False, alsolocal=True, localanononly=True,
                     revoke_local_talk=False):
        """Apply a global block.
        
        :param target: (string) Target IP address or IP range in CIDR format
        :param reason: (string) Reason for global block
        :param expiry: (string) Expiry time of block
        :param anononly: (boolean) Apply global block to anon users only
        :param modify: (boolean) Modify existing block
        :param alsolocal: (boolean) Apply a local block additionally to global
        :param localanononly: (boolean) Apply local block to anon users only
        :param revoke_local_talk: (boolean) Revoke talk page access locally
        """
        token = self.get_token()
        query = self.query.copy()
        query.update({
            'action': 'globalblock',
            'target': target,
            'reason': reason,
            'expiry': expiry,
            'anononly': anononly,
            'modify': modify,
            'alsolocal': alsolocal,
            'localanononly': localanononly,
            'localblockstalk': revoke_local_talk,
            'token': token
        })
        resp = requests.post(
            self.url,
            params=query,
            auth=self.oauth
        )
        self.handle_resp(resp)  # Check for errors

    def log(self, type=None, action=None, user=None, limit=10):
        """Get a set of log entries.

        :param type: (string) Type of log to fetch
        :param action: (string) Type of log action to fetch
        :param user: (string) User to filter bytearray
        :param limit: (int) Max number of entries to fetch
        :return: (list) Containing dicts of log entries
        """
        query = self.query.copy()
        query['list'] = 'logevents'
        if type is not None:
            query['letype'] = type
        if action is not None:
            query['leaction'] = action
        if user is not None:
            query['user'] = user
        query['lelimit'] = limit
        resp = requests.get(
            self.url,
            params=query,
            auth=self.oauth
        )
        resp = self.handle_resp(resp)
        return resp['query']['logevents']


class ConnectionError(Exception):
    """Connection did not have a 200 status."""

    pass


class ApiError(Exception):
    """The Api returned some error."""

    pass
