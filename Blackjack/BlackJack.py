from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.ext import db
from google.appengine.ext.webapp import template

import random
import os
import json

class Game(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty()
    players_max = ndb.IntegerProperty()
    players_current = ndb.IntegerProperty()
    deck = ndb.StringProperty(repeated=True)
    cards_dealt = ndb.StringProperty(repeated=True)

class Player(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty(required=True)
    tokens = ndb.IntegerProperty()
    avatar_url = ndb.StringProperty()
    cards_visible = ndb.StringProperty(repeated=True)
    cards_not_visible = ndb.StringProperty(repeated=True)

class Game_Status():
    valid_actions = ndb.StringProperty(repeated=True)
    cards_visible = ndb.StringProperty(repeated=True)
    common_cards_visible = ndb.StringProperty(repeated=True)
    players = ndb.StringProperty(repeated=True)

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        rows = Game.query()
        path = os.path.join(os.path.dirname(__file__), 'html/active_games.html')
        self.response.out.write(template.render(path, {'rows': rows}))
    def post(self):
        game = Game(name = self.request.get("name"),
                    players_max = int(self.request.get("players_max")),
                    identifier = random.randint(0, 1000000),
                    players_current = 0,
                    deck = [],
                    cards_dealt = [])
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
        player_stringified = json.dumps({
                                 "name": player.name, 
                                 "identifier": player.identifier,
                                 "avatar_url": player.avatar_url,
                                 "tokens": player.tokens
                             })
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(player_stringified)

class JoinPlayer(webapp.RequestHandler):
    def post(self, game_id):
        self.response.out.write(game_id)
    
class PlayerStatus(webapp.RequestHandler):
    def post(self, game_id):
        self.response.out.write(game_id)
         
class VisibleTable(webapp.RequestHandler):
    def post(self, game_id):
        self.response.out.write(game_id)
        
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
