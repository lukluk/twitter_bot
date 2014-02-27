import os
import json
import requests
import gevent
from greenlet_node import Node, NodeEventLoop
import TwitterAPI
from gevent import monkey
monkey.patch_all()

auth = {'access_token_key': os.environ['TW_ACCESS_TOKEN_2'],
        'access_token_secret': os.environ['TW_ACCESS_TOKEN_SECRET_2'],
        'consumer_key': os.environ['TW_API_KEY_2'],
        'consumer_secret': os.environ['TW_API_SECRET_2']}

api = TwitterAPI.TwitterAPI(**auth)


class Tweet(object):
    __slots__ = ('id', 'url', 'hashtag', 'response')

    def __init__(self, id, url, hashtag, response=None):
        self.id = id
        self.url = url
        self.hashtag = hashtag
        self.response = response


class TweetNode(Node):

    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)
        self.hashtag = "scoreme"

        self.connect(api.request('user').get_iterator().__iter__(), type="input")

        self.start()

    def _get_is_valid(self, packet):

        try:
            return packet is not None and \
                   packet.get('text') is not None and \
                   packet['entities'].get('hashtags') is not None and \
                   self.hashtag in set([ht.get('text') for ht in packet['entities'].get('hashtags')]) and \
                   packet['entities'].get('urls') is not None

        except AttributeError:
            return False

    def _process_packet(self, packet):
        print packet
        id = packet.get('id')
        entities = packet.get('entities')
        if entities.get("urls"):
            url = entities.get('urls')[0]['expanded_url']
            hashtags = set([ht.get('text') for ht in entities.get('hashtags')])
            packet = Tweet(id=id, hashtag=hashtags, url=url)

            return packet

    def _do_output(self, packet):
        GooglePageSpeedAPINode(starting_packets=[packet], timeout_seconds=20)


class GooglePageSpeedAPINode(NodeEventLoop):

    def __init__(self, max_attempts=3, *args, **kwargs):

        self.max_attempts = max_attempts

        proxy = os.environ['QUOTAGUARDSTATIC_URL']
        self.proxy_dict = {"http": proxy, "https": proxy, "ftp": proxy}
        self.G_KEY = os.environ['GOOGLE_PUBLIC_API_ACCESS_SEVER']

        NodeEventLoop.__init__(self, *args, **kwargs)
        self.start()

    def _process_packet(self, packet):

        attempts = 0
        resp = {}

        url = packet.url

        while attempts < self.max_attempts or resp.get('responseCode', 400) > 200:
            attempts += 1

            req = "https://www.googleapis.com/pagespeedonline/v1/runPagespeed?url=%s&key=%s" % (url, self.G_KEY)
            resp = requests.get(url=req, proxies=self.proxy_dict)
            resp = json.loads(resp.text)

        packet.response = resp
        return packet

    def _do_output(self, packet):

        api.request('statuses/update', {'status': 'The website %r has a score of %r' %
                                                  (packet.url, packet.response.get('score')),
                                        "in_reply_to_status_id": id})

T = TweetNode(run_frequency=1)
while True:
    gevent.sleep(1)
