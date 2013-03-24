from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.ext import db
from google.appengine.ext.webapp import template

import random
import os

class Game(ndb.Model):
    name = ndb.StringProperty(required=True)
    identifier = ndb.IntegerProperty()
    players_max = ndb.IntegerProperty()
    players_current = ndb.IntegerProperty()
    deck = ndb.StringProperty(repeated=True)
    cards_dealt = ndb.StringProperty(repeated=True)

class Player(ndb.Model):
    name = db.StringProperty(required=True)
    identifier = db.StringProperty(required=True)
    tokens = db.IntegerProperty()
    avatar_url = db.StringProperty()
    cards_visible = db.StringListProperty()
    cards_not_visible = db.StringListProperty()

class Game_Status():
    valid_actions = db.StringListProperty()
    cards_visible = db.StringListProperty()
    common_cards_visible = db.StringListProperty()
    players = db.StringListProperty()

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

app = webapp.WSGIApplication(
          [('/games', MainPage)],
           debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
