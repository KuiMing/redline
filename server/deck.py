import random


class Deck:
    def __init__(self, cards):
        self.draw_pile = cards[:]
        self.discard_pile = []
        random.shuffle(self.draw_pile)

    def draw(self, n=1):
        drawn = []
        for _ in range(n):
            if not self.draw_pile:
                self._reshuffle()
            if not self.draw_pile:
                break
            drawn.append(self.draw_pile.pop())
        return drawn

    def discard(self, cards):
        self.discard_pile.extend(cards)

    def _reshuffle(self):
        if self.discard_pile:
            self.draw_pile = self.discard_pile[:]
            self.discard_pile = []
            random.shuffle(self.draw_pile)
