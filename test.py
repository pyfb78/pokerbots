import eval7

deck = eval7.Deck()
deck.shuffle()
a = deck.deal(1)
print(a[0], a[0].rank)