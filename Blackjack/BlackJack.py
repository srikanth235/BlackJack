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

deck = ['2s', '2h', '2d', '2c', '3s', '3h', '3d', '3c',
        '4s', '4h', '4d', '4c', '5s', '5h', '5d', '5c',
        '6s', '6h', '6d', '6c', '7s', '7h', '7d', '7c',
        '8s', '8h', '8d', '8c', '9s', '9h', '9d', '9c',
        '10s', '10h', '10d', '10c', 'Js', 'Jh', 'Jd', 'Jc',
        'Qs', 'Qh', 'Qd', 'Qc', 'Ks', 'Kh', 'Kd', 'Kc',
        'As', 'Ah', 'Ad', 'Ac']

# Game states
REGISTERING = "Registering"
STARTED = "Starting"
FILLED = "Slots Filled"
ENDED = "Ended"

# Player states
JOIN = "Join"
PLAY = "Play"
WON = "Won"
LOST = "Lost"
VIEW = "View"

client_list =[]
def get_value(card):
    if card[0] in ['J', 'Q', 'K']:
        return 10
    return int(card[0])

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
        if 'A' != card:
            value = value + get_value(card)
        else:
            num_aces = num_aces + 1
    for i in range(num_aces):
        if value + (num_aces - 1 - i) + 11 <= 21:
            value = value + 11
        else:
            value = value + 1
    return value

def get_next_action(player, tokens):
    prev_actions = player.actions_taken
    hand_value = player.hand_value
    player_bet = player.bet
    actions = []
    if hand_value >= 21:
        actions = []
    elif len(prev_actions) == 0 or has_only_bet(prev_actions):
        actions = actions + get_bet_actions(tokens)
        if len(prev_actions) > 0:
            actions.append("Deal")
    elif prev_actions[-1] == "Deal":
        actions = ["Stand", "Hit"]
        if player_bet * 2 >= tokens:
            actions.append("Double") 
    elif prev_actions[-1] == "Double":
        actions = [ "Hit"]
    elif prev_actions[-1] == "Hit" and "Double" in prev_actions:
        actions = ["Stand"]
    else:
        actions = ["Hit", "Stand"]
    return actions

class Game(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty()
    players_max = ndb.IntegerProperty()
    players_current = ndb.IntegerProperty()
    deck = ndb.StringProperty(repeated=True)
    common_cards = ndb.StringProperty(repeated=True)
    common_cards_visible = ndb.StringProperty(repeated=True)
    players = ndb.IntegerProperty(repeated=True)
    status = ndb.StringProperty();


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


class CreateGame(webapp.RequestHandler):
    def get(self):
        if(self.request.get("name","") == ""):
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
                    status=REGISTERING)
        game.put()

    
class DisplayGames(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        rows = Game.query()
        path = os.path.join(os.path.dirname(__file__), 'active_games.html')
        self.response.out.write(template.render(path, {'rows': rows}))


class StartGame(webapp.RequestHandler):
    def post(self):
        game = Game.query(Game.identifier == int(self.request.get("game_id"))).fetch(1)[0]
        game.status = "Started"
        game.put()
        self.response.out.write("Done")


class CreatePlayer(webapp.RequestHandler):
    def post(self):
        player = Player(name=self.request.get("name"),
                    identifier=random.randint(0, 1000000),
                    avatar_url=self.request.get("avatar_url"),
                    tokens=int(self.request.get("tokens"))
                 )
        player.put()
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
        cur_player = simplejson.loads(self.request.get("player"))
        # inserts row into games model
        game = (Game.query(Game.identifier == game_id).fetch(1))[0]
        if game.status != REGISTERING:
            return self.redirect("/games")
        else:
            game.players.append(cur_player["identifier"]) 
            game.players_current = game.players_current + 1
            if game.players_current == game.players_max:
                game.status = FILLED
                game.put()

        # inserts row into players model
        player = (Player.query(Player.identifier == int(cur_player["identifier"])).fetch(1))[0]
        player.games.append(game_id)
        player.put()
        # inserts row into Status Player
        status = Game_Player_Status(game_id=game_id,
                                    player_id=player.identifier,
                                    cards=[],
                                    actions_taken=[],
                                    bet=0,
                                    hand_value=0,
                                    status=PLAY)
        status.put()


class PlayerStatus(webapp.RequestHandler):
    def post(self, game_id):
        game_id = int(game_id)
        game = Game.query(Game.identifier == game_id).fetch(1)[0]
        cur_player = simplejson.loads(self.request.get("player"))
        player_id = int(cur_player["identifier"])
        if player_id in game.players:
            player_status = Game_Player_Status.query(ndb.AND(
                            Game_Player_Status.game_id == game_id,
                            Game_Player_Status.player_id == player_id)).fetch() 
            self.response.out.write(player_status)
        elif game.status == REGISTERING:
            self.response.out.write(JOIN)
        else:
            self.response.out.write("-")


class VisibleTable(webapp.RequestHandler):
    def get(self, game_id):
        game_id = int(game_id)
        game_players = Game_Player_Status.query(
                           Game_Player_Status.game_id == game_id).fetch()
        count = len(game_players)
        dealer = (Game.query(Game.identifier == game_id).fetch(1))[0]
        path = os.path.join(os.path.dirname(__file__), 'blackjackgame.html')
        self.response.out.write(template.render(path,
                                    {'players': game_players,
                                     'count': count,
                                     'dealer_cards': dealer.common_cards
                                    }))


class GameAction(webapp.RequestHandler):
    def multicast(self, message, self_id):
        for client_id in client_list:
            if client_id != self_id:
                channel.send_message(client_id, message)
    def remove_random_card(self, game_id):
        game = Game.query(Game.identifier == game_id).fetch(1)[0]
        random.shuffle(game.deck)
        card = game.deck.pop()
        game.put()
        return card

    def update_player_info(self, player_info, value):
        player_info.tokens = player_info.tokens - value
        player_info.put()

    def post(self, game_id):
        game_id = int(game_id)
        action = self.request.get("action", "None")
        player_id = int(simplejson.loads(self.request.get("player"))["identifier"])
        
        cur_player = Game_Player_Status.query(ndb.AND(
                         Game_Player_Status.game_id == game_id,
                         Game_Player_Status.player_id == player_id)).fetch(1)[0]

        player_info = Player.query(Player.identifier == player_id).fetch(1)[0]
        value = int(self.request.get("value", 2 * cur_player.bet))
        new_cards = []
        if action.startswith("Bet") or action == "Double":
            self.update_player_info(player_info, value)           
            cur_player.bet = cur_player.bet + value
        elif action == "Deal":
            new_cards.append(self.remove_random_card(game_id))
            new_cards.append(self.remove_random_card(game_id))
            cur_player.cards = cur_player.cards + new_cards
        elif action == "Hit":
            new_cards.append(self.remove_random_card(game_id))
            cur_player.cards = cur_player.cards + new_cards

        cur_player.hand_value = get_hand_value(cur_player.cards)
        cur_player.actions_taken.append(action)
        cur_player.put()
        actions = get_next_action(cur_player, player_info.tokens)
        dealer = (Game.query(Game.identifier == game_id).fetch(1))[0]
        player_stringified = simplejson.dumps({
                                   'actions': actions,
                                   'tokens': player_info.tokens,
                                   'cards': new_cards
                            })
        self_id = str(game_id)+ '-' + str(player_id)
        message = simplejson.dumps({'action': action, 'cards': new_cards, 'id': str(player_id)})
        self.multicast(message, self_id);
        self.response.out.write(player_stringified)

class GamePlay(webapp.RequestHandler):
    def get(self, game_id):
        game_id = int(game_id)
        if(self.request.get("player", "-1") != "-1"):
            player_id = int(simplejson.loads(self.request.get("player"))
                            ["identifier"])
        else:
            player_id = -1
        game_players = Game_Player_Status.query(ndb.AND(
                          Game_Player_Status.game_id == game_id,
                          Game_Player_Status.player_id != player_id)).fetch()
        count = len(game_players)
        dealer = (Game.query(Game.identifier == game_id).fetch(1))[0]
        if player_id != -1:
            cur_player = Game_Player_Status.query(ndb.AND(
                         Game_Player_Status.game_id == game_id,
                         Game_Player_Status.player_id == player_id)).fetch(1)[0]
            player_info = Player.query(Player.identifier == player_id).fetch(1)[0]
            tokens = player_info.tokens
            dealer_cards = dealer.common_cards_visible
            actions = get_next_action(cur_player, tokens)
            token_suffix = player_id
        else:
            actions = []
            tokens = None
            dealer_cards = dealer.common_cards
            cur_player = None
            token_suffix = random.randint(0, 1000000)
        dealer = (Game.query(Game.identifier == game_id).fetch(1))[0]
        path = os.path.join(os.path.dirname(__file__), 'blackjackgame.html')
        channel_token = channel.create_channel(str(game_id) + "-" + str(token_suffix)) 
        self.response.out.write(template.render(path,
                                  {'players': game_players,
                                   'count': count,
                                   'dealer_cards': dealer_cards,
                                   'actions': actions,
                                   'tokens': tokens,
                                   'game_id': game_id,
                                   'cur_player': cur_player,
                                   'channel_token': channel_token
                                  }))


class AddClient(webapp.RequestHandler):
     def post(self):
         global client_list
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
