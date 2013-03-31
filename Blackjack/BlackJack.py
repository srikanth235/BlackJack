import simplejson
import random
import os
import threading
import datetime

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import channel
from google.appengine.api import memcache

deck = ['2s', '2h', '2d', '2c', '3s', '3h', '3d', '3c',
        '4s', '4h', '4d', '4c', '5s', '5h', '5d', '5c',
        '6s', '6h', '6d', '6c', '7s', '7h', '7d', '7c',
        '8s', '8h', '8d', '8c', '9s', '9h', '9d', '9c',
        '10s', '10h', '10d', '10c', 'Js', 'Jh', 'Jd', 'Jc',
        'Qs', 'Qh', 'Qd', 'Qc', 'Ks', 'Kh', 'Kd', 'Kc',
        'As', 'Ah', 'Ad', 'Ac']

# Game states
REGISTERING = "Registering"
FILLED = "Slots Filled"
STARTED = "Started"
DEALER_COMPLETED = "Dealer Completed"
ENDED = "Ended"

# Player states
JOIN = "Join"
PLAY = "Play"
END = "End"
WON = "Won"
LOST = "Lost"
VIEW = "View"
TIE = "Tie"
STOP = "Stop"

YES = "Yes"
NO = "No"

client_list = []
round_players = {}


def get_value(card):
    if card[0] in ['J', 'Q', 'K']:
        return 10
    if len(card) == 2:
        return int(card[0])
    else:
        return int(card[0:2])


def has_only_bet(actions):
    for action in actions:
        if not str(action).startswith("Bet"):
            return False
    return True


def get_bet_actions(tokens):
    actions = []
    if tokens >= 1:
        actions.append("Bet 1")
    if tokens >= 5:
        actions.append("Bet 5")
    if tokens >= 25:
        actions.append("Bet 25")
    if tokens >= 100:
        actions.append("Bet 100")
    if tokens >= 500:
        actions.append("Bet 500")
    return actions


def get_hand_value(cards):
    value = 0
    num_aces = 0
    for card in cards:
        if 'A' != card[0]:
            value = value + get_value(card)
        else:
            num_aces = num_aces + 1
    for i in range(num_aces):
        if value + (num_aces - 1 - i) + 11 <= 21:
            value = value + 11
        else:
            value = value + 1
    # is busted
    if value > 21:
        value = 1000
    return value


def get_next_action(player, tokens):
    prev_actions = player.actions_taken
    hand_value = get_hand_value(player.cards)
    player_bet = player.bet
    actions = []
    if hand_value >= 21:
        return []
    elif len(prev_actions) == 0 or has_only_bet(prev_actions):
        actions = actions + get_bet_actions(tokens)
        if len(prev_actions) > 0:
            actions.append("Deal")
    elif prev_actions[-1] == "Deal":
        actions = ["Stand", "Hit"]
        if player_bet * 2 >= tokens:
            actions.append("Double")
    elif prev_actions[-1] == "Double":
        actions = ["Hit"]
    elif prev_actions[-1] == "Hit" and "Double" in prev_actions:
        actions = ["Stand"]
    elif prev_actions[-1] == "Stand":
        actions = []
    else:
        actions = ["Hit", "Stand"]
    return actions


def get_server_move(cards):
    dealer_value = get_hand_value(cards)
    if dealer_value > 17:
        return []
    elif dealer_value == 0:
        return ["Deal"]
    else:
        return ["Hit"]


def broadcast(message, client_id=-1):
    clients = []
    if(client_id != -1 and client_id in client_list):
        clients = [client_id]
    else:
        clients = client_list
    for client_id in clients:
        channel.send_message(client_id, message)


def remove_random_card(game_id):
    game = retrieve_game_entity(game_id)
    random.shuffle(game.deck)
    card = game.deck.pop()
    game.put()
    return card


def retrieve_game_player_entity(game_id, player_id):
    return Game_Player_Status.query(ndb.AND(
                        Game_Player_Status.game_id == game_id,
                        Game_Player_Status.player_id == player_id)).fetch(1)[0]


def retrieve_player_entity(player_id):
    player = memcache.get(str(player_id))
    if player is not None:
        return player
    return Player.query(Player.identifier == player_id).fetch(1)[0]


def retrieve_game_entity(game_id):
    return Game.query(Game.identifier == game_id).fetch(1)[0]


@ndb.transactional
def update_game_player_entity(game_player):
    game_player.put()


@ndb.transactional
def update_player_entity(player):
    player.put()
    memcache.add(str(player.identifier), player, 1)


@ndb.transactional
def update_game_entity(game):
    game.put()
    memcache.add(str(game.identifier), game, 1)


def get_client_id(game_id, player_id):
    return str(game_id) + "-" + str(player_id)


def calc_player_result(dealer, game_player):
    dealer_value = get_hand_value(dealer.common_cards)
    player_value = get_hand_value(game_player.cards)
    if dealer_value == player_value:
        return 0, TIE
    elif player_value == 1000:
        return 0, LOST
    elif dealer_value == 1000:
        return game_player.bet, WON
    elif dealer_value > player_value:
        return 0, LOST
    else:
        return game_player.bet, WON


def update_game_status(game_id):
    remaining_players = Game_Player_Status.query(ndb.AND(
                            Game_Player_Status.game_id == game_id,
                            Game_Player_Status.status == PLAY
                        )).fetch()
    game = retrieve_game_entity(game_id)
    if len(remaining_players) == 0 and game.status == DEALER_COMPLETED:
        game.status = ENDED
        update_game_entity(game)


def update_game(game_id, player_id=-1):
        player_id = int(player_id)
        game_id = int(game_id)
        dealer = retrieve_game_entity(game_id)
        dealer_cards = dealer.common_cards
        if player_id == -1:
            game_players = Game_Player_Status.query(
                        Game_Player_Status.game_id == game_id).fetch()
        else:
            game_players = [retrieve_game_player_entity(game_id, player_id)]
        status = ""
        for game_player in game_players:
            player = retrieve_player_entity(game_player.player_id)
            player_id = player.identifier
            client_id = get_client_id(game_id, player_id)
            stat = dealer.status
            if game_player.status == STOP and stat == DEALER_COMPLETED:
                win_tokens, status = calc_player_result(dealer, game_player)
                player.tokens = player.tokens + 2 * win_tokens
                game_player.status = status
                if win_tokens > 0:
                    update_player_entity(player)
                    message = simplejson.dumps({
                                            'game_id': str(game_id),
                                            'player_id': str(player_id),
                                            'tokens': player.tokens
                                           })
                    broadcast(message, client_id)
                if status in [WON, LOST, TIE]:
                    message = simplejson.dumps({'game_id': str(game_id),
                                                'player_id': str(player_id),
                                                'status': status
                                           })
                    broadcast(message, client_id)
            elif game_player.status == PLAY:
                actions = get_next_action(game_player, player.tokens)
                message = simplejson.dumps({'game_id': str(game_id),
                                            'player_id': str(player_id),
                                            'actions': actions})
                broadcast(message, client_id)
                game_player.can_play = YES
            update_game_player_entity(game_player)
        update_game_status(game_id)
        return status


class Game(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty()
    players_max = ndb.IntegerProperty()
    players_current = ndb.IntegerProperty()
    deck = ndb.StringProperty(repeated=True)
    common_cards = ndb.StringProperty(repeated=True)
    common_cards_invisible = ndb.StringProperty(repeated=True)
    players = ndb.IntegerProperty(repeated=True)
    status = ndb.StringProperty()


class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty(required=True)
    tokens = ndb.IntegerProperty()
    avatar_url = ndb.StringProperty()
    games = ndb.IntegerProperty(repeated=True)


class Game_Player_Status(ndb.Model):
    game_id = ndb.IntegerProperty()
    player_id = ndb.IntegerProperty()
    cards = ndb.StringProperty(repeated=True)
    actions_taken = ndb.StringProperty(repeated=True)
    bet = ndb.IntegerProperty()
    hand_value = ndb.IntegerProperty()
    status = ndb.StringProperty()
    can_play = ndb.StringProperty()


class CreateGame(webapp.RequestHandler):
    def get(self):
        if(self.request.get("name", "") == ""):
            rows = Game.query()
            path = os.path.join(os.path.dirname(__file__), 'create_game.html')
            self.response.out.write(template.render(path, {'rows': rows}))
            return
        game = Game(name=self.request.get("name"),
                    players_max=int(self.request.get("players_max")),
                    identifier=random.randint(0, 1000000),
                    players_current=0,
                    deck=deck,
                    common_cards=[],
                    common_cards_invisible=[],
                    status=REGISTERING)
        update_game_entity(game)


class DisplayGames(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        rows = Game.query()
        path = os.path.join(os.path.dirname(__file__), 'active_games.html')
        self.response.out.write(template.render(path, {'rows': rows}))


class StartGame(webapp.RequestHandler):
    def post(self):
        game_id = int(self.request.get("game_id"))
        game = retrieve_game_entity(game_id)
        game.status = "Started"
        new_cards = []
        new_cards.append(remove_random_card(game_id))
        new_cards.append(remove_random_card(game_id))
        game.common_cards = []
        new_cards = [ '2s', '2h']
        game.common_cards_invisible = new_cards
        update_game_entity(game)
        global round_players
        players = []
        game_players = Game_Player_Status.query(
                       Game_Player_Status.game_id == game_id).fetch()
        for player in game_players:
            players.append(player.player_id)
        round_players[game_id] = players
       # self.response.out.write(round_players[game_id])


class CreatePlayer(webapp.RequestHandler):
    def post(self):
        player = Player(name=self.request.get("name"),
                    identifier=random.randint(0, 1000000),
                    avatar_url=self.request.get("avatar_url"),
                    tokens=int(self.request.get("tokens"))
                 )
        update_player_entity(player)
        player_stringified = simplejson.dumps({
                                 'name': player.name,
                                 'identifier': player.identifier,
                                 'avatar_url': player.avatar_url,
                                 'tokens': player.tokens
                             })
        self.response.out.write(player_stringified)


class JoinPlayer(webapp.RequestHandler):
    def post(self, game_id):
        game_id = int(game_id)
        player_id = simplejson.loads(self.request.get("player"))["identifier"]
        player_id = int(player_id)
        # inserts row into games model
        game = retrieve_game_entity(game_id)
        if game.status != REGISTERING:
            return self.redirect("/games")
        else:
            game.players.append(player_id)
            game.players_current = game.players_current + 1
            if game.players_current == game.players_max:
                game.status = FILLED
            update_game_entity(game)

        # inserts row into players model
        player = retrieve_player_entity(player_id)
        player.games.append(game_id)
        update_player_entity(player)

        # inserts row into Status Player
        game_player = Game_Player_Status(game_id=game_id,
                                         player_id=player.identifier,
                                         cards=[],
                                         actions_taken=[],
                                         bet=0,
                                         hand_value=0,
                                         status=PLAY,
                                         can_play=YES)
        message = simplejson.dumps({'game_id': str(game_id),
                                    'player_id': str(player_id),
                                    'join': 'joined'})
        broadcast(message)
        update_game_player_entity(game_player)


class PlayerStatus(webapp.RequestHandler):
    def post(self, game_id):
        game_id = int(game_id)
        game = retrieve_game_entity(game_id)
        cur_player = simplejson.loads(self.request.get("player"))
        player_id = int(cur_player["identifier"])
        if player_id in game.players:
            player = retrieve_game_player_entity(game_id, player_id)
            self.response.out.write(player.status)
        elif game.status == REGISTERING:
            self.response.out.write(JOIN)
        else:
            self.response.out.write("Can only view")


class VisibleTable(webapp.RequestHandler):
    def get(self, game_id):
        game_id = int(game_id)
        game_players = Game_Player_Status.query(
                           Game_Player_Status.game_id == game_id).fetch()
        count = len(game_players)
        dealer = retrieve_game_entity(game_id)
        path = os.path.join(os.path.dirname(__file__), 'blackjackgame.html')
        self.response.out.write(template.render(path,
                                    {'players': game_players,
                                     'count': count,
                                     'dealer_cards': dealer.common_cards
                                    }))


class GameAction(webapp.RequestHandler):
    def wake_up_server(self, game_id, player_id=-1):
        global round_players
        if player_id != -1:
            round_players[game_id].remove(player_id)
        #does server need to play
        if len(round_players[game_id]) == 0:
            game = retrieve_game_entity(game_id)
            action = get_server_move(game.common_cards)
            new_cards = []
            if len(game.common_cards_invisible) > 0:
                new_cards = game.common_cards_invisible
                game.common_cards_invisible = []
            else:
                new_cards.append(remove_random_card(game_id))
            message = simplejson.dumps({
                            'game_id': str(game_id),
                            'cards': new_cards,
                            'player_id': 'dealer'})
            broadcast(message)
            game.common_cards = game.common_cards + new_cards
            if get_hand_value(game.common_cards) >= 17:
                game.status = DEALER_COMPLETED
            update_game_entity(game)
            update_game(game_id)
            player_list = Game_Player_Status.query(ndb.AND(
                                        Game_Player_Status.game_id == game_id,
                                        Game_Player_Status.status == PLAY
                                        )).fetch()
            round_players[game_id] = []
            for player in player_list:
                round_players[game_id].append(player.player_id)
            hvalue = get_hand_value(game.common_cards)
            if len(round_players[game_id]) == 0: 
                if hvalue < 17:
                    self.wake_up_server(game_id, -1)
            

    def post(self, game_id):
        game_id = int(game_id)
        action = self.request.get("action")
        request_player = self.request.get("player")
        player_id = int(simplejson.loads(request_player)["identifier"])
        game_player = retrieve_game_player_entity(game_id, player_id)
        value = int(self.request.get("value", 2 * game_player.bet))
        player = retrieve_player_entity(player_id)
        new_cards = []
        tokens = player.tokens
        dealer = retrieve_game_entity(game_id)
        if action.startswith("Bet") or action == "Double":
            player.tokens = tokens - value
            update_player_entity(player)
            game_player.bet = game_player.bet + value
        elif action == "Deal":
            new_cards.append(remove_random_card(game_id))
            new_cards.append(remove_random_card(game_id))
        elif action == "Hit":
            new_cards.append(remove_random_card(game_id))
        if dealer.status == DEALER_COMPLETED or (not action.startswith("Bet")):
            game_player.can_play = NO
        else:
            game_player.can_play = YES

        game_player.cards = game_player.cards + new_cards
        game_player.actions_taken.append(action)
        if len(get_next_action(game_player, tokens)) == 0:
            game_player.status = STOP
            game_player.can_play = NO
        update_game_player_entity(game_player)
        player_stringified = simplejson.dumps({
                                'game_id': str(game_id),
                                'player_id': str(player_id),
                                'cards': new_cards
                            })
        broadcast(player_stringified)
        self.response.out.write(simplejson.dumps({'game_id': game_id,
                                                  'player_id': player_id,
                                                  'tokens': player.tokens}))
        if dealer.status == DEALER_COMPLETED or game_player.can_play == YES:
                status = update_game(game_id, player_id)
        else:
            self.wake_up_server(game_id, player_id)


class GamePlay(webapp.RequestHandler):
    def get(self, game_id):
        game_id = int(game_id)
        is_anonymous = True
        player_id = -1
        if(self.request.get("player", "-1") != "-1"):
            player_id = int(simplejson.loads(self.request.get("player"))
                            ["identifier"])
            is_anonymous = False
        game_players = Game_Player_Status.query(ndb.AND(
                          Game_Player_Status.game_id == game_id)).fetch()
        count = len(game_players)
        dealer = retrieve_game_entity(game_id)

        actions = []
        if not is_anonymous:
            cur_player = retrieve_game_player_entity(game_id, player_id)
            player_info = retrieve_player_entity(player_id)
            tokens = player_info.tokens
            dealer_cards = dealer.common_cards
            if cur_player.can_play == YES:
                actions = get_next_action(cur_player, tokens)
            token_suffix = player_id
        else:
            dealer_cards = dealer.common_cards + dealer.common_cards_invisible
            cur_player = None
            token_suffix = random.randint(0, 1000000)
            tokens = 0

        path = os.path.join(os.path.dirname(__file__), 'blackjackgame.html')
        client_id = str(game_id) + "-" + str(token_suffix)
        channel_token = channel.create_channel(client_id)
        self.response.out.write(template.render(path,
                                  {'players': game_players,
                                   'count': count,
                                   'dealer_cards': dealer_cards,
                                   'actions': actions,
                                   'tokens': tokens,
                                   'cur_player_id': player_id,
                                   'game_id': game_id,
                                   'channel_token': channel_token
                                  }))


class AddClient(webapp.RequestHandler):
    def post(self):
        global client_list
        client_id = self.request.get('from')
        if client_id not in client_list:
            client_list.append(self.request.get('from'))


class DeleteClient(webapp.RequestHandler):
    def post(self):
        global client_list
        client_list.remove(self.request.get('from'))

app = webapp.WSGIApplication(
          [('/create_game', CreateGame),
          ('/games', DisplayGames),
          ('/start_game', StartGame),
          ('/player', CreatePlayer),
          (r'/game/(.*)/playerConnect', JoinPlayer),
          (r'/game/(.*)/status', PlayerStatus),
          (r'/game/(.*)/visible_table', GamePlay),
          (r'/game/(.*)/play', GamePlay),
          (r'/game/(.*)/action', GameAction),
          ('/_ah/channel/connected/', AddClient),
          ('/_ah/channel/disconnected/', DeleteClient)],
           debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
