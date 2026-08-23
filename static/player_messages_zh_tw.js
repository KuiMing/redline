(() => {
  'use strict';

  const messages = Object.freeze({
    // Lobby and room lifecycle.
    'Game not found': '找不到遊戲房間。',
    'Name required': '請輸入玩家名稱。',
    'Room full': '房間已滿。',
    'Need at least 2 players': '至少需要 2 名玩家才能開始。',
    'Only host can start': '只有房主可以開始遊戲。',
    'All players must be ready before start': '所有玩家都需要先按下準備。',
    'All players must choose factions first': '所有玩家都必須先選擇陣營。',
    'Exactly one player must choose red_army': '必須恰好有 1 名玩家選擇紅軍。',
    'Player not found in lobby': '在作戰室中找不到該玩家。',
    'Faction category already taken': '這個陣營類別已被其他玩家選擇。',
    'Invalid base option': '這個根據地選項無效。',
    'Choose faction before ready': '請先選擇陣營與根據地，再按準備。',
    'Game not ready': '遊戲尚未準備完成。',
    'Defender not found': '找不到防守玩家。',
    'Player not found': '找不到玩家。',
    'Proof players not found': '找不到測試驗證所需的玩家。',

    // Generic selection and stale-state errors.
    'Invalid choice index': '選擇項目無效，請重新選擇。',
    'Invalid choice count': '選擇數量不正確。',
    'Duplicate choice indices': '不能重複選擇同一項。',
    'No pending choice': '目前沒有待處理的選擇。',
    'Not your pending choice': '這不是你目前需要處理的選擇。',
    'This choice cannot be cancelled': '這個選擇不能取消。',
    'Unsupported pending choice type': '目前無法處理這種類型的選擇。',
    'Invalid target choice': '目標選擇無效。',
    'Invalid town choice': '城鎮選擇無效。',
    'Invalid choice': '選擇無效。',
    'Invalid index': '選擇位置無效。',
    'Invalid choice count': '選擇數量不正確。',
    'Please resolve the pending choice first': '請先處理目前待選擇效果。',
    'Resolve pending choice before advancing phase': '請先處理待選擇效果，再進入下一階段。',
    'Resolve pending choice before building': '請先處理待選擇效果，再建立組織。',
    'Resolve pending build choice before building elsewhere': '請先完成目前的建立選擇，再到其他地方建立組織。',

    // Card zones, deck and purchase area.
    'Purchase deck unavailable': '購買牌庫目前無法使用。',
    'Purchase deck empty': '購買牌庫已空。',
    'Deck empty': '牌庫已空。',
    'Chosen card not in discard pile': '選擇的卡牌不在棄牌堆中。',
    'Chosen card not in hand': '選擇的卡牌不在手牌中。',
    'Chosen card missing': '找不到選擇的卡牌。',
    'Chosen action card not in hand': '選擇的行動卡不在手牌中。',
    'Chosen action card changed': '選擇的行動卡狀態已改變，請重新選擇。',
    'Chosen purchase-area card missing': '購買區中的指定卡牌已不存在。',
    'Chosen card not in purchase area': '選擇的卡牌不在購買區。',
    'Chosen card not in deck': '選擇的卡牌不在牌庫中。',
    'Chosen card not in trash': '選擇的卡牌不在移除區中。',
    'Unsupported trash source': '目前不支援從這個區域移除卡牌。',
    'Unsupported optional trash source': '目前不支援從這個區域選擇移除卡牌。',
    'Inspected deck cards changed': '已查看的牌庫卡牌狀態已改變，請重新操作。',
    'No qualifying card to discard': '沒有符合條件的卡牌可棄。',
    'No hand card to bottom-deck': '沒有手牌可以放到牌庫底。',
    'No cards selected': '尚未選擇任何卡牌。',
    'Duplicate purchase index': '不能重複購買同一個位置的卡牌。',
    'No card in slot': '這個購買位置沒有卡牌。',
    'Static purchase card is out of supply': '這張常設購買卡已無庫存。',
    'Not enough resources': '資源不足。',
    'Card not found': '找不到卡牌。',
    'Card play mode must be resource or action': '請選擇將卡牌用作資源或行動。',
    'Hand': '手牌',
    'Discard pile': '棄牌堆',
    'Purchase area': '購買區',
    'Random market': '隨機購買區',
    'Skip': '略過',
    'Cancel': '取消',
    'Confirm': '確認',
    'Draw': '抽牌',
    'Discard': '棄牌',

    // Players and targets.
    'Target player not found': '找不到目標玩家。',
    'Target town not found': '找不到目標城鎮。',
    'Target player has no hand cards': '目標玩家沒有手牌。',
    'Target player has no organization within range': '目標玩家在範圍內沒有組織。',
    'Target player is not within range': '目標玩家不在效果範圍內。',
    'Target player is not valid for era effect': '這名玩家不是時代效果的合法目標。',
    'Target organization is not within era range': '目標組織不在時代效果範圍內。',
    'No target organization within range': '範圍內沒有可選擇的目標組織。',
    'No valid target': '目前沒有合法目標。',
    'No valid State Security target': '國安部：目前沒有可以瓦解的組織（僅限紅軍組織 1 格內的牆內組織）。',
    'Invalid target': '目標無效。',
    'Invalid discard target': '棄牌目標無效。',
    'Invalid dissolve target': '瓦解目標無效。',
    'Invalid imitate target': '模仿目標無效。',
    'Invalid Red Army target': '紅軍目標無效。',
    'No legal target for interactive support card': '這張奧援卡目前沒有合法目標。',

    // Organization build, dissolve and movement.
    'Cannot build in enemy-occupied or invalid town': '不能在敵方占領或無效的城鎮建立組織。',
    'Invalid build town': '建立組織的城鎮無效。',
    'Invalid own organization to sacrifice': '選擇犧牲的己方組織無效。',
    'No enemy organization within range of sacrificed organization': '犧牲組織的範圍內沒有敵方組織。',
    'Missing sacrificed organization': '找不到原本要犧牲的組織。',
    'Target organization is not within range of sacrificed organization': '目標組織不在犧牲組織的範圍內。',
    'Target organization is no longer within range': '目標組織已不在效果範圍內。',
    'Target cannot be replaced with an organization': '瓦解後無法在目標城鎮建立組織。',
    'Target could not be replaced after dissolve': '目標瓦解後無法完成組織建立。',
    'No era builds remaining': '目前沒有剩餘的時代效果建立次數。',
    'Era build town already has your organization': '這個時代效果目標城鎮已有你的組織。',
    'No valid era build towns': '沒有符合時代效果的建立城鎮。',
    'Invalid town': '城鎮無效。',
    'Town required': '請選擇城鎮。',
    'No organization in town': '該城鎮沒有組織。',
    'No organization in origin': '起點城鎮沒有你的組織。',
    'No organization in target town': '目標城鎮沒有組織。',
    'Cannot develop in this town': '不能在這個城鎮建立組織。',
    'Target out of build range': '目標城鎮超出建立範圍。',
    'Current event restricts building organizations': '目前事件限制建立組織。',
    'Red Army base has been destroyed and cannot be rebuilt': '紅軍根據地已被摧毀，不能再次建立組織。',
    'Origin and target required': '請選擇起點與目標。',
    'Origin and destination required': '請選擇起點與目的地。',
    'Origin and destination must differ': '起點與目的地不能相同。',
    'Invalid move mode': '移動方式無效。',
    'Cannot move into occupied town': '不能移入已有組織的城鎮。',
    'Red Army organization cannot leave Red Army development space': '紅軍組織不能離開紅軍發展空間。',
    'Not enough move points': '移動次數不足。',
    'Base anchor organization cannot move': '根據地的錨定組織不能移動。',
    'Only Hong Kong can relocate its base': '只有香港陣營可以遷移根據地。',
    'Base is already there': '根據地已位於該城鎮。',
    'Cannot relocate base into occupied town': '不能把根據地遷移到已有組織的城鎮。',
    'Airport base relocation requires your ACTION phase': '機場遷移根據地必須在你的行動階段進行。',
    'Not enough move points (airport base relocation costs 2)': '移動次數不足；機場遷移根據地需要 2 次移動。',

    // Support, reactions and flow ownership.
    'Support card context missing': '找不到奧援卡效果的必要狀態。',
    'Invalid support mode': '奧援卡模式無效。',
    'Unsupported support flow step': '目前無法處理這個奧援卡步驟。',
    'Support card cannot be restored': '無法將奧援卡恢復到手牌。',
    'Unsupported support interaction result': '目前無法處理這個奧援卡互動結果。',
    'Invalid reaction card': '取消牌無效。',
    'Unsupported spy card': '目前不支援這張間諜卡。',

    // Turn phases and faction abilities.
    'Not in BASE_SELECTION phase': '目前不是根據地選擇階段。',
    'No pending base choice for player': '這名玩家目前沒有待處理的根據地選擇。',
    'Invalid base choice': '根據地選擇無效。',
    'Base already taken': '這個根據地已被其他玩家選擇。',
    'Faction action already used this turn': '本回合已使用過陣營能力。',
    "Player's faction does not have this ability": '你的陣營沒有這項能力。',
    'Guess required': '請先選擇猜測結果。',
    'Unknown faction action': '未知的陣營能力。',
    'Not in ACTION phase': '目前不是行動階段。',
    'Not in PURCHASE phase': '目前不是購買階段。',
  });

  const patterns = Object.freeze([
    [/^Not enough move points \(need (\d+)\)$/i, match => `移動次數不足；需要 ${match[1]} 次移動。`],
    [/^No road connection$/i, () => '起點與目標之間沒有道路連線。'],
    [/^No rail connection$/i, () => '起點與目標之間沒有鐵路連線。'],
    [/^Base already taken: (.+)$/i, match => `以下根據地已被選擇：${match[1]}`],
    [/^Unknown queued era: .+$/i, () => '找不到排程中的時代關卡。'],
    [/^Could not activate queued era: .+$/i, () => '無法啟動排程中的時代關卡。'],
    [/^Unknown era: .+$/i, () => '找不到指定的時代關卡。'],
    [/^Era cannot use lifecycle proof setup: .+$/i, () => '這個時代關卡不支援目前的驗證情境。'],
    [/^Era did not activate through lifecycle: .+$/i, () => '時代關卡未能依正常流程啟動。'],
    [/^Need at least (\d+) faction ids$/i, match => `至少需要 ${match[1]} 個陣營。`],
    [/^scenario must be (.+)$/i, () => '測試情境參數無效。'],
    [/^Invalid (.+) choice$/i, () => '選擇無效，請重新操作。'],
    [/^Unsupported (.+)$/i, () => '目前不支援這項操作。'],
  ]);

  function playerMessageZhTw(value, fallback = '操作失敗，請重新確認目前狀態後再試。') {
    const text = String(value ?? '').trim();
    if (!text) return '';
    if (Object.prototype.hasOwnProperty.call(messages, text)) return messages[text];
    for (const [pattern, render] of patterns) {
      const match = text.match(pattern);
      if (match) return render(match);
    }
    return /[A-Za-z]{3,}/.test(text) ? fallback : text;
  }

  window.REDLINE_PLAYER_MESSAGE_ZH_TW = messages;
  window.playerMessageZhTw = playerMessageZhTw;
})();
