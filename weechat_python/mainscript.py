# -*- coding: utf-8 -*-

import unicodedata
from functools import partial
import string
import random
random = random.SystemRandom()
import re
import os
import pipes
import time
import subprocess
from datetime import datetime, timedelta
import json
import shlex

import weechat
weechat.register("main", "Nitori", "1.0", "GPL", "All major scripts.", "", "")

import weechat_utils
from weechat_utils import hook_signal, hook_irc_command, color
from weechat_utils import infolist_get, hook_timer, hook_process

from other_utils import to_seconds, seconds_to_string, simple_tobytes

# index of nyaa_list
last_nyaas = []
last_nyaa_users = []

nyaa_list = [
    u'sends hords of catgirls over {}.',
    u'sends hords of evil catgirls over {}.',
    u'sends hords of ninja catgirls over {}.',
    u'sends hords of anti terror catgirls over {}.',
    u'sends hords of anti troll catgirls over {}.',
    u'sends hords of nerd catgirls over {}.',
    u'sends hords of seme catgirls over {}.',
    u'sends hords of hacker catgirls over {}.',
    u'sends hords of vampire catgirls over {}.',
    u'sends hords of loli catgirls over {}.',
    u'sends hords of futanari catgirls over {}.',
    u'sends hords of nude catgirls over {}.',
    u'sends hords of lesbian catgirls over {}.',
    u'sends hords of bull dyke catgirls over {}.',
    u'sends hords of strict catgirls over {}.',
    u'sends hords of catgirls in school uniforms with short skirts over {}.',
    u'sends hords of meido catgirls over {}.',
    u'sends hords of nurse catgirls over {}.',
    u'sends hords of black haired catgirls over {}.',
    u'sends hords of lullaby singing catgirls over {}.',
    u'sends hords of Hatsune Miku catgirls over {}.',
    u'sends hords of catgirls with giant boobies over {}.',
    u'sends hords of flat chested catgirls over {}.',
    # u'sends hords of hexchat loving catgirls over {}.',
    u'sends hords of anti proprietary catgirls over {}.',
    # u'and hords of catgirls sing “Happy Birthday dear {}”.'
]

url_fetch_data = {
    'locked': False,
    'cache': {},
    'current_proc': None,
    'max_cache_time': 24*60*60,
    'url_title_cache': {},
    'url_pattern': re.compile(r'''
        (?:
            (?P<p1>\() | (?P<p2>\{) | (?P<p3>\<)
        | (?P<p4>\[) | (?P<p5>") | (?P<p6>')
        )?
            (?P<url>https?://\S+)
        (?(p6)')(?(p5)")(?(p4)\])(?(p3)\>)(?(p2)\})(?(p1)\))
    ''', re.X),
    'ignore_list': [
        re.compile(r'.*bot.*!.*@.*$', re.I),
        re.compile(r'.*!.*bot.*@.*$', re.I),
        re.compile(r'.*!.*@.*bot.*$', re.I),
        re.compile(r'sdk_backup.*!.*@.*$', re.I),
        re.compile(r'.*Shanghai.*!.*@.*$', re.I),
        re.compile(r'the_new_moon!.*@.*$', re.I),
        re.compile(r'thomasbot!.*@.*$', re.I),
        re.compile(r'samohtbot!.*@.*$', re.I),
        re.compile(r'Xjs\|moonshine!.*@.*$', re.I),
        re.compile(r'ChanServ!.*@.*$', re.I),
        re.compile(r'n\|ki!.*@.*$', re.I),
        re.compile(r'Lukelty!.*@.*$', re.I),
        re.compile(r'Marlen_Jackson!.*@.*$', re.I),
        re.compile(r'mufubot!.*@.*$', re.I),
        re.compile(r'crubitch!.*@.*$', re.I),
        re.compile(r'y!.*@.*$', re.I),
        re.compile(r'MsTasty!.*@.*$', re.I),
        re.compile(r'.*!mstasty@.*$', re.I),
        re.compile(r'Lyekka!.*@.*$', re.I),
        re.compile(r'Peaches!.*@.*\.cloud-ips\.com$', re.I),
        re.compile(r'\|\^-\^\|!.*@.*$', re.I),
    ]
}

google_data = {'locked_until': 0}
yuri_data = {'locked_until': 0}
jisho_data = {'locked_until': 0}

timer_filename = os.path.expanduser('~/.weechat/python/data/_timerdata.txt')


def load_timers():
    with open(timer_filename, 'r') as fp:
        try:
            timer_data = json.load(fp)
        except:
            timer_data = {'timers': [], 'next': 1}
    return simple_tobytes(timer_data)


def save_timers(timer_data):
    with open(timer_filename, 'w') as fp:
        json.dump(timer_data, fp)


def add_timer(time_seconds, userdata):
    now = int(time.time())
    timer_data = load_timers()
    _ud = {k: v for k, v in userdata.items()}

    tid = timer_data['next']
    timer_data['next'] += 1
    ctx = _ud['ctx']
    _ud['ctx'] = {'server': ctx.server, 'channel': ctx.channel}
    timer_data['timers'].append(dict(
        tid=tid,
        hook=_ud['hook'],
        when=now+time_seconds,
        time_seconds=time_seconds,
        userdata=_ud,
    ))
    save_timers(timer_data)
    return tid


def remove_timer(tid, unhook=True):
    timer_data = load_timers()
    new_timers = []
    found = False
    for timer in timer_data['timers']:
        if timer['tid'] == tid:
            found = True
            if unhook:
                weechat.unhook(timer['hook'])
            continue
        new_timers.append(timer)
    timer_data['timers'] = new_timers
    save_timers(timer_data)
    return found


def cmd_timer_callback(userdata):
    """Callback for +timer command."""
    remove_timer(userdata['tid'], False)
    userdata['ctx'].command('/say {}, I remind you of: {} ({} ago)'.format(
        userdata['caller'],
        userdata['message'] or "whatever you wanted to be reminded of",
        seconds_to_string(userdata['time_seconds'])))


# loading existing timers from file
if not os.path.exists(timer_filename):
    with open(timer_filename, 'w') as fp:
        json.dump({'timers': [], 'next': 1}, fp)

timer_data = load_timers()
for timer in timer_data['timers']:
    now = int(time.time())
    _ud = timer['userdata']
    fake_context = weechat_utils.Context(_ud['ctx']['server'],
                                         _ud['ctx']['channel'])
    _ud['ctx'] = fake_context
    _ud['time_seconds'] = timer['time_seconds']
    _ud['tid'] = timer['tid']
    hook = hook_timer(max(1, timer['when'] - now), cmd_timer_callback, _ud)
    _ud['hook'] = hook

MAX_TIMER_LENGTH = 60 * 60 * 24 * 7 * 4  # in seconds


@hook_irc_command('+timer')
def timer_hook(ctx, pline, userdata):
    caller = pline.prefix.nick
    args = pline.trailing.split(None, 2)
    usage = '/notice {} Invalid syntax: +timer <[ digits "h" ]' \
            '[ digits "m" ][ digits "s" ]> [<message>]'.format(caller)

    if len(args) < 2:
        ctx.command(usage)
        return
    elif len(args) == 2:
        _, time_string = args
        message = None
    else:
        _, time_string, message = args

    time_seconds = to_seconds(time_string)
    if not time_seconds:
        ctx.command(usage)
        return

    if time_seconds > MAX_TIMER_LENGTH:
        ctx.command('/notice {} Too large, maximum is {} seconds or {}'
                    .format(caller, MAX_TIMER_LENGTH, seconds_to_string(MAX_TIMER_LENGTH)))
        return

    _userdata = dict(
        ctx=ctx,
        caller=caller,
        message=message,
        time_seconds=time_seconds
    )
    hook = hook_timer(time_seconds, cmd_timer_callback, _userdata)
    _userdata['hook'] = hook
    tid = add_timer(time_seconds, _userdata)
    _userdata['tid'] = tid

    dt = datetime.now() + timedelta(seconds=time_seconds)
    ctx.command('/notice {} timer set to {} seconds ({}, Timer Id: {}, around: {})'.format(
        caller, time_seconds, seconds_to_string(time_seconds), tid, dt.strftime('%Y-%m-%d %H:%M:%S')))


@hook_irc_command('+deltimer')
def del_timer(ctx, pline, userdata):
    caller = pline.prefix.nick
    args = pline.trailing.split(None, 1)
    if len(args) != 2:
        ctx.command('/notice {} Timer ID missing.'.format(caller))
        return
    _, tid = args
    try:
        tid = int(tid)
    except ValueError:
        ctx.command('/notice {} Timer Id must be an integer.'.format(caller))
        return
    timer_data = load_timers()
    for timer in timer_data['timers']:
        ud = timer['userdata']
        if timer['tid'] == tid:
            if caller.lower() == ud['caller'].lower():
                remove_timer(tid, unhook=True)
                ctx.command('/notice {} Timer removed.'.format(caller))
            else:
                ctx.command('/notice {} This timer belongs to {}.'
                            .format(caller, ud['caller']))
            break
    else:
        ctx.command('/notice {} Timer not found.'.format(caller))


@hook_irc_command('+jisho', userdata=jisho_data)
def jisho_hook(ctx, pline, userdata):
    if time.time() < userdata['locked_until']:
        return

    def _jisho_process_cb(returncode, stdout, stderr, _userdata):
        if returncode == 0:
            stdout = stdout.strip()
            if not stdout:
                return
            ctx.command('/say {}'.format(stdout))

    args = pline.trailing.split()
    args.pop(0)
    if args:
        userdata['locked_until'] = time.time() + 3
        param = ' '.join(args)
        hook_process(['jisho.py', param], _jisho_process_cb)


@hook_irc_command('+yuri', userdata=yuri_data)
def yuri_hook(ctx, pline, userdata):
    if time.time() < userdata['locked_until']:
        return

    def _yuri_process_cb(returncode, stdout, stderr, _userdata):
        if returncode == 0:
            stdout = stdout.strip()
            if not stdout:
                return
            dyn = json.loads(stdout)
            tag_string = u' '.join(u'[{}]'.format(tag) for tag in dyn[u'tags'])
            dyn[u'tag_string'] = tag_string
            ctx.command(
                '/say \x02Your random yuri chapter |\x02 {title} \x02by\x02'
                ' {authors} | {link} | \x02{tag_string}\x02'
                .format(**dyn))

    userdata['locked_until'] = time.time() + 5
    hook_process(['yuri.py'], _yuri_process_cb)


@hook_irc_command('+google', userdata=google_data)
def google_hook(ctx, pline, userdata):
    if time.time() < userdata['locked_until']:
        return

    def _google_process_cb(returncode, stdout, stderr, _userdata):
        if returncode == 0:
            stdout = stdout.strip()
            if not stdout:
                return
            ctx.command(
                '/say \x02you\'re feeling lucky |\x02 {}'.format(stdout))

    args = pline.trailing.split()
    args.pop(0)
    if args:
        userdata['locked_until'] = time.time() + 5
        param = ' '.join(args)
        hook_process(['im-feeling-lucky.py', param], _google_process_cb)


@hook_irc_command('+?')
def inc_ask(ctx, pline, userdata):
    fn = '~/.weechat/python/data/' + ctx.server + '_' + ctx.channel + '.txt'
    fn = fn.lower()
    fn = os.path.expanduser(fn)
    count = 0
    if os.path.exists(fn):
        with open(fn, 'r') as fp:
            count = int(fp.read().strip())
    ctx.command(u'/say = {}'.format(count))


@hook_irc_command('+1')
def inc_one(ctx, pline, userdata):
    fn = '~/.weechat/python/data/' + ctx.server + '_' + ctx.channel + '.txt'
    fn = fn.lower()
    fn = os.path.expanduser(fn)
    count = 0
    if os.path.exists(fn):
        with open(fn, 'r') as fp:
            count = int(fp.read().strip())
    count += 1
    ctx.command(u'/say +{}'.format(count))
    with open(fn, 'w') as fp:
        fp.write(str(count))


@hook_irc_command('+flipcoin')
def flipcoin(ctx, pline, userdata):
    val = random.randrange(100)
    if val % 2 == 0:
        ctx.command(u'/say Head!')
    else:
        ctx.command(u'/say Tail!')


@hook_irc_command('+timestamp')
def timestamp(ctx, pline, userdata):
    args = pline.trailing.split()
    args.pop(0)  # pop "+timestamp"
    if args:
        try:
            ts = float(args.pop(0))
        except ValueError:
            return
        dt = datetime.fromtimestamp(ts)
        ctx.command(u'/say {}'.format(str(dt)))


@hook_irc_command('+decide')
def decide(ctx, pline, userdata):
    line = pline.trailing[7:]
    #args = [s.strip('!?.,') for s in line.split()]
    args = shlex.split(line)
    if not args:
        ctx.command(u'/say Nothing to choose from.')
    else:
        random.shuffle(args)
        choice = random.choice(args)
        ctx.command(
            u'/say I chose: {}'.format(choice.decode('utf-8', 'replace')))


@hook_irc_command('+nyaa', userdata=(nyaa_list, last_nyaa_users))
def nyaa(ctx, pline, ud):
    nyaa_list, last_nyaa_users = ud
    args = pline.trailing.split(None, 1)
    if len(args) == 1:
        mylist = infolist_get(
            "irc_nick", "{},{}".format(ctx.server, ctx.channel))
        nicklist = [user.name for user in mylist if ctx.nickname != user.name]
        nick = random.choice(nicklist)
        if len(nicklist) > len(last_nyaa_users):
            while nick.lower() in last_nyaa_users:
                nick = random.choice(nicklist)
        last_nyaa_users.append(nick.lower())
        last_nyaa_users = last_nyaa_users[-min(5, len(nicklist)):]

        target = nick.decode('utf-8')
    else:
        target = u' '.join(arg.strip() for arg in args[1:]).decode('utf-8')

    while True:
        index = random.randrange(len(nyaa_list))
        if index not in last_nyaas:
            break
    last_nyaas.append(index)
    if len(last_nyaas) > 5:
        last_nyaas.pop(0)
    ctx.command(u"/me {}".format(nyaa_list[index].format(target)))


@hook_irc_command('+kill')
def kill(ctx, pline, userdata):
    args = pline.trailing.split(None, 1)
    if len(args) == 1:
        mylist = infolist_get(
            "irc_nick", "{},{}".format(ctx.server, ctx.channel))
        nicklist = list(set(user.name for user in mylist) -
                        set([ctx.nickname]))
        nick = random.choice(nicklist)
        ctx.command(u"/me makes {} disappear with her SUKIYUKI CHING CHANG SPIRIT BEAM.".format(nick.strip()))
    else:
        ctx.command(u"/me makes {} disappear with her SUKIYUKI CHING CHANG SPIRIT BEAM.".format(args[1].strip()))


@hook_irc_command('+poo')
def poo(ctx, pline, userdata):
    args = pline.trailing.split(None, 1)
    if len(args) == 1:
        mylist = infolist_get(
            "irc_nick", "{},{}".format(ctx.server, ctx.channel))
        nicklist = list(set(user.name for user in mylist) -
                        set([ctx.nickname]))
        nick = random.choice(nicklist)
        ctx.command(u"/me throws 💩 at {}.".format(nick.strip()))
    else:
        ctx.command(u"/me throws 💩 at {}.".format(args[1].strip()))


@hook_irc_command('+unicode')
def unicode(ctx, pline, userdata):
    args = pline.trailing.split()[1:]
    if not args:
        ctx.command('/say No symbol given.')
        return

    if args[0].startswith('U+'):
        codepoint = int(args[0][2:], 16)
        char = unichr(codepoint)
        try:
            name = unicodedata.name(char)
        except ValueError:
            name = 'n/a'
        if codepoint < 32:
            char = '-'
        ctx.command(u'/say {}, Name: {}'.format(char, name))
        return

    reststr = ' '.join(args)
    if all(char in string.ascii_uppercase + string.digits + ' -'
           for char in reststr):
        try:
            char = unicodedata.lookup(reststr.strip())
        except KeyError:
            pass
        else:
            codepoint = ord(char)
            ctx.command(u'/say {}, Codepoint: U+{:X}'.format(char, codepoint))
            return

    symbol = args[0].decode(ctx.encoding)
    nfc_symbol = unicodedata.normalize(u'NFC', symbol)
    if len(nfc_symbol) > 1:
        ctx.command('/say Too many symbols.')
        return
    try:
        name = unicodedata.name(nfc_symbol)
    except TypeError:
        ctx.command('/say Unknown character or invalid input.')
        return
    except ValueError:
        name = 'n/a'
    nfd_symbol = unicodedata.normalize(u'NFD', symbol)
    category = unicodedata.category(symbol)
    codepoint = ord(nfc_symbol)
    outstr = u'Codepoint: U+{:X}, Name: {}, Category: {}.'.format(codepoint, name, category)
    if len(nfd_symbol) > len(nfc_symbol):
        outstr += u' (Compose: '
        slist = []
        for char in nfd_symbol:
            codepoint = ord(char)
            slist.append(
                u'U+{:X}'.format(codepoint))
        outstr += u', '.join(slist) + ')'
    ctx.command(u'/say {}'.format(outstr))


@hook_irc_command('+clear', userdata=url_fetch_data)
def force_fetch(ctx, pline, url_fetch_data):
    args = pline.trailing.split()
    args.pop(0)
    if not args:
        ctx.command('/say No URL specified.')
        return

    url = args[0]
    if '#' in url:
        url = url[:url.find('#')]
    if url in url_fetch_data['url_title_cache']:
        del url_fetch_data['url_title_cache'][url]
        ctx.command('/say Removed URL from cache.')
    else:
        ctx.command('/say URL was not in cache.')


def url_requests_unlock(url_fetch_data):
    url_fetch_data['locked'] = False


def process_cb(returncode, stdout, stderr, url_fetch_data):
    if returncode == 0:
        ctx = url_fetch_data['priv_ctx']
        info_string = stdout.strip()
        url_fetch_data['url_title_cache'][url_fetch_data['url']] = \
            (time.time() + url_fetch_data['max_cache_time'], info_string)
        if info_string:
            ctx.command('/say \x02url_info |\x02 {}'.format(info_string))
    hook_timer(2, url_requests_unlock, url_fetch_data)


def clean_cache(url_fetch_data):
    url_title_cache = url_fetch_data['url_title_cache']
    old_len = len(url_title_cache)
    url_title_cache = {
        k: v for k, v in url_title_cache.iteritems() if v[0] > time.time()
    }
    if old_len > len(url_title_cache):
        weechat.prnt("", "Cleared {} cached urls.".format(
            old_len - len(url_title_cache)))
    url_fetch_data['url_title_cache'] = url_title_cache
    hook_timer(30*60, clean_cache, url_fetch_data)
    return weechat.WEECHAT_RC_OK

# execute this once now.
hook_timer(30*60, clean_cache, url_fetch_data)


@hook_signal('privmsg', userdata=url_fetch_data)
def privmsg(ctx, pline, signal, url_fetch_data):
    ctx.to_channel(pline.middle[0])
    if url_fetch_data['locked']:
        return

    if not ctx.is_channel(pline.middle[0]):
        return

    if pline.trailing.startswith('+'):
        return

    if re.search(r'https?://', pline.trailing) is None:
        return

    if any(pattern.match(pline.prefix.raw) for
           pattern in url_fetch_data['ignore_list']):
        # weechat.prnt("", "Ignored {}".format(pline.prefix.mask))
        return

    match = url_fetch_data['url_pattern'].search(pline.trailing)
    if match is None:
        return

    url = match.group('url')
    if '#' in url:
        url = url[:url.find('#')]
    url_fetch_data['locked'] = True

    # is it still cached?
    data = url_fetch_data['url_title_cache'].get(url, None)
    if data:
        ts, info_string = data
        if time.time() >= ts:
            del url_fetch_data['url_title_cache'][url]
        else:
            if info_string:
                ctx.command('/say \x02url_info |\x02 {}'.format(info_string))
            hook_timer(2, url_requests_unlock, url_fetch_data)
            return

    url_fetch_data['proc_output'] = ''
    url_fetch_data['proc_errput'] = ''
    url_fetch_data['url'] = url
    url_fetch_data['priv_ctx'] = ctx
    hook_process(['fetch-url-title.py', url], process_cb,
                 userdata=url_fetch_data)
