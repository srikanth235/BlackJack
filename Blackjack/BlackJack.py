from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.ext import db
import random

class Game(ndb.Model):
    name = db.StringProperty(required=True)
    identifier = db.IntegerProperty(required=True)
    players_max = db.IntegerProperty(required=True)
    players_current = db.IntegerProperty(required=True)
    deck = db.StringListProperty(required=True)
    cards_dealt = db.StringListProperty(required=True)

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
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Hello, webapp World!')
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        out.write(template.render(path, {'rows': rows, 'desc': desc, 'status': status_ships}))
    def post(self):
        game = Game(name=self.request.get("name"),
                    players_max = self.request.get("players_max"),
                    identifier = random.randint(0, 1000000)
                    players_current = 0,
                    deck = [],
                    cards_dealt = [])
        game.put()
        self.response.out.write("Game created successfully")

app = webapp.WSGIApplication(
          [('/games', MainPage)],
           debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
