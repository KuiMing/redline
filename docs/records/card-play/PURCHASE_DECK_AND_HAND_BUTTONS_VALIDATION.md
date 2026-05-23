# Purchase deck / hand buttons validation

- purchase deck excludes static cards in sample_53 and all_cards: passed
- static area contains 宣傳家 / 思想家 / 資助者 / 資本家 / 分神 / 內鬥 only: passed
- play_card resource mode mutates resources/hand/discard: passed
- play_card action mode mutates hand/discard: passed
- hand card buttons use bound event listeners instead of inline playHandCard onclick: passed
