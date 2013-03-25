from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.ext import db
from google.appengine.ext.webapp import template

import simplejson
import random
import os

deck = ['2s', '2h', '2d', '2c', '3s', '3h', '3d', '3c', '4s', '4h', '4d', '4c', '5s', '5h', '5d', '5c', 
        '6s', '6h', '6d', '6c', '7s', '7h', '7d', '7c', '8s', '8h', '8d', '8c', '9s', '9h', '9d', '9c', 
        '10s', '10h', '10d', '10c', 'Js', 'Jh', 'Jd', 'Jc', 'Qs', 'Qh', 'Qd', 'Qc', 'Ks', 'Kh', 'Kd', 'Kc', 
        'As', 'Ah', 'Ad', 'Ac'];
class Game(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty()
    players_max = ndb.IntegerProperty()
    players_current = ndb.IntegerProperty()
    deck = ndb.StringProperty(repeated=True)
    common_cards = ndb.StringProperty(repeated=True)
    players = ndb.IntegerProperty(repeated=True)

class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty(required=True)
    tokens = ndb.IntegerProperty()
    avatar_url = ndb.StringProperty()
    games = ndb.IntegerProperty(repeated=True)

class Game_Player_Status(ndb.Model):
    game_id = ndb.IntegerProperty()
    player_id = ndb.IntegerProperty()
    cards_visible = ndb.StringProperty(repeated=True)
    cards = ndb.StringProperty(repeated=True)
    actions_taken = ndb.StringProperty(repeated=True)

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        rows = Game.query()
        path = os.path.join(os.path.dirname(__file__), 'active_games.html')
        self.response.out.write(template.render(path, {'rows': rows}))
    def post(self):
        game = Game(name = self.request.get("name"),
                    players_max = int(self.request.get("players_max")),
                    identifier = random.randint(0, 1000000),
                    players_current = 0,
                    deck = deck,
                    common_cards = [])
        game.put()
        self.response.out.write(
                     "<html><body><h2>"
                     + self.request.get("name")
                     + " created successfully</body></html>")

class CreatePlayer(webapp.RequestHandler):
    def post(self):
        player = Player(name = self.request.get("name"),
                    identifier = random.randint(0, 1000000),
                    avatar_url = self.request.get("avatar_url"),
                    tokens = int(self.request.get("tokens"))
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
        game.players.append(cur_player["identifier"])
        game.players_current = game.players_current + 1
        game.put()
        # inserts row into players model
        player = (Player.query(Player.identifier == int(cur_player["identifier"])).fetch(1))[0]
        player.tokens = player.tokens - 10
        player.games.append(game_id)
        player.put()
        # inserts row into Status Player 
        status = Game_Player_Status(game_id = game_id, player_id = player.identifier, 
                                    cards_visible = ['10d','10c'], cards = ['10d','10c'], actions_taken = [])
        status.put()
        self.response.out.write(simplejson.dumps({"cards":status.cards_visible}))
        
class PlayerStatus(webapp.RequestHandler):
    def post(self, game_id):
        game_id = int(game_id)
        game = Game.query(Game.identifier == game_id).fetch(1)[0]
        cur_player = simplejson.loads(self.request.get("player"))
        if int(cur_player["identifier"]) in game.players:
            self.response.out.write("Play")
        elif len(game.common_cards) == 0 and game.players_max != game.players_current:
            self.response.out.write("Join")
        else:
            self.response.out.write("View")

class VisibleTable(webapp.RequestHandler):
    def get(self, game_id):
        game_id = int(game_id)
        game_players = Game_Player_Status.query(Game_Player_Status.game_id == game_id).fetch()
        count = len(game_players);
        dealer = (Game.query(Game.identifier == game_id).fetch(1))[0]
        path = os.path.join(os.path.dirname(__file__), 'blackjackgame.html')
        self.response.out.write(template.render(path, {'players' : game_players, 'count' : count, 'dealer_cards' : dealer.common_cards}))

class GameAction(webapp.RequestHandler): 
    def post(self, game_id):
        self.response.out.write(game_id)

app = webapp.WSGIApplication(
          [('/games', MainPage),
          ('/player', CreatePlayer),
          (r'/game/(.*)/playerConnect', JoinPlayer),
          (r'/game/(.*)/status', PlayerStatus),
          (r'/game/(.*)/visible_table', VisibleTable),
          (r'/game/(.*)/action', GameAction)],
           debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
