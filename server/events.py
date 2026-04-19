import random


class EventDeck:
    def __init__(self, events):
        self.draw_pile = events[:]
        random.shuffle(self.draw_pile)
        self.discard_pile = []

    def draw(self):
        if not self.draw_pile:
            self._reshuffle()
        if not self.draw_pile:
            return None
        card = self.draw_pile.pop()
        self.discard_pile.append(card)
        return card

    def _reshuffle(self):
        if self.discard_pile:
            self.draw_pile = self.discard_pile[:]
            self.discard_pile = []
            random.shuffle(self.draw_pile)
