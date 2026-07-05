# 一帶一路南洋 browser proof

- Base URL: http://127.0.0.1:8000
- Normal generic-build path: pending event_build_organization resolved, 紅軍在曼谷有 1 組織，phase advances to end/purchase.
- Stale visual-build recovery path: 曼谷已有紅軍組織但 pending_choice 仍存在時，再按曼谷會清空 pending_choice，不重複建立，phase advances to end/purchase.
- Stale advance-button recovery path: 曼谷已有紅軍組織但 pending_choice 仍存在時，直接按開始購買階段也會自動清空 pending_choice 並進入 end/purchase.
- Screenshot (normal_generic_build): /Users/benmini/.openclaw/workspace/redline/docs/records/event-cards/belt-road-red-turn-build-gating-20260706_064635/normal_generic_build_after_bangkok_build_purchase_phase.png
- Screenshot (stale_recovery): /Users/benmini/.openclaw/workspace/redline/docs/records/event-cards/belt-road-red-turn-build-gating-20260706_064635/stale_recovery_after_bangkok_build_purchase_phase.png
- Screenshot (stale_advance_recovery): /Users/benmini/.openclaw/workspace/redline/docs/records/event-cards/belt-road-red-turn-build-gating-20260706_064635/stale_advance_recovery_after_bangkok_build_purchase_phase.png
