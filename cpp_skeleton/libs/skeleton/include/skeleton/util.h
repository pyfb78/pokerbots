#pragma once

#include <algorithm>
#include <sstream>
#include <array>
#include <vector>
#include <map>

namespace pokerbots::skeleton {

template <typename Container> bool isEmpty(Container &&c) {
  return std::all_of(c.begin(), c.end(), [](auto &&v) { return v.empty(); });
}

template <typename Iterator>
std::string join(const Iterator begin, const Iterator end, const std::string &separator) {
  std::ostringstream oss;
  for (Iterator it = begin; it != end; ++it) {
    if (it != begin)
      oss << separator;
    oss << *it;
  }
  return oss.str();
}

// Note: the state must be a round_state
std::array<bool, 2> get_bounty_hits(std::shared_ptr<const State> round_state)
{
    /*
    Determines if each player hit their bounty card during the round.

    A bounty is hit if the player's bounty card rank appears in either:
    - Their hole cards
    - The community cards dealt so far

    Returns:
        std::array<bool, 2>: A tuple containing two booleans where:
            - First boolean indicates if Player 1's bounty was hit
            - Second boolean indicates if Player 2's bounty was hit
    */
   //         ranks = {'2':0, '3':1, '4':2, '5':3, '6':4, '7':5, '8':6, '9':7, 'T':8, 'J':9, 'Q':10, 'K':11, 'A':12}
    std::map<std::string, int> ranks = {
        {"2", 0}, {"3", 1}, {"4", 2}, {"5", 3}, {"6", 4}, {"7", 5}, {"8", 6}, {"9", 7}, {"T", 8}, {"J", 9}, {"Q", 10}, {"K", 11}, {"A", 12}
    };
    auto state = std::static_pointer_cast<const RoundState>(round_state);
    std::vector<int> cards0, cards1;
    for(int i = 0; i < 2; i ++)
        cards0.push_back(ranks[state->hands[0][i]]);
    for(int i = 0; i < 2; i ++)
        cards1.push_back(ranks[state->hands[1][i]]);
    for(int i = 0; i < state->street; i ++)
    {
        cards0.push_back(ranks[state->deck[i]]);
        cards1.push_back(ranks[state->deck[i]]);
    }
    std::array<bool, 2> bounty_hits = {
        std::find(cards0.begin(), cards0.end(), state->bounties[0]) != cards0.end(), 
        std::find(cards1.begin(), cards1.end(), state->bounties[1]) != cards1.end() 
    };
    return bounty_hits;
}

} // namespace pokerbots::skeleton
