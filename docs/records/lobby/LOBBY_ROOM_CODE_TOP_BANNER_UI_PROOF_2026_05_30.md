# Lobby room-code top banner UI proof — 2026-05-30

- Screenshot: `docs/records/lobby/LOBBY_ROOM_CODE_TOP_BANNER_UI_2026_05_30.png`
- URL: `http://127.0.0.1:8000/?proof=lobby-room-banner-2026-05-30-final`
- Room code used in proof: `bf13bae8-00df-47dd-a333-24e102ff1993`

## Flow verified

1. Created a room through the official browser UI.
2. Confirmed the room code appears as a top sticky banner: `房間代碼 ... 複製 ... 分享給其他玩家加入`.
3. Chose Red Army, then Beijing base.
4. Clicked `確認陣營` successfully.
5. Confirmed `我已準備` became enabled.

## Browser state evidence

- `bannerAboveFaction`: `true`
- `confirmClickable`: `true`
- `readyEnabled`: `true`
- `readyClickable`: `true`
- Banner rect: `{x: 174, y: 65, w: 932, h: 55, b: 120}`
- Faction picker rect: `{x: 231, y: 397, w: 818, h: 167, b: 564}`
- Confirm button hit-test: `confirmFactionBtn`
- Ready button hit-test: `toggleReadyBtn`

The screenshot is an original browser capture. Vision analysis failed after capture, so this record pairs the original screenshot with direct browser DOM/hit-test evidence.
