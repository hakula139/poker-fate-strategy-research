# Hidden-card delivery

## Evidence and conclusion

The reported symptom is an opponent apparently knowing private hole cards or community cards before reveal. No live hand, packet capture, or server implementation was available. Static analysis confirms where disclosed cards enter client memory and identifies server boundaries to audit. It does not establish that ordinary players receive opponents' unrevealed cards or future betting-street cards.

The source belongs to the [Android 1.7.0 artifact](../../reference/artifacts/android-1.7.0.md). The [artifact record](../../reference/artifacts/android-1.7.0.json) maps decoded filenames to source locations and hashes. Citations use one-based line ranges in those decoded files.

## Transport and normal delivery

`Net.lua:64-102` parses a received WebSocket packet, calls `pb.decode`, fills protocol defaults, invokes `net[name]`, and then emits the UI event. Models therefore change before UI animations start. Received values are available inside the client even when an animation has not displayed them.

`CSHoldem.proto:17-38` separates per-street `RoundStartBRC.board` from `HandCardRSP.card1..card4` and `seatid`. `net_pk.lua:28-35` calls `PKData:updateSelfCard`. Despite its name, that function uses an explicitly received seat ID when present (`PKData.lua:199-223`). This supports per-seat delivery, including legitimate observation. It does not establish broadcast to every player.

`net_pk.lua:64-75` adds received public cards to the model immediately. `PKData.lua:144-161` copies every supplied value without truncating by street. `PKTable.lua:610-710` subsequently chooses the flop, turn, or river animation from the received stage. The inspected normal path contains no requirement to preload future streets.

`ShowHandRSP` contains per-seat cards (`CSHoldem.proto:84-96`). Its handler installs those cards and clears the fold flag (`net_pk.lua:96-113`). `PKTable.lua:1060-1079` then flips them and computes card types. This is consistent with a showdown disclosure path. Correct audience and timing remain server responsibilities.

## Confirmed visual timing distinction

`PKTable.lua:665-678` deliberately replaces the already-received river card with a card back during an all-in effect and reveals it after 1.6 seconds. `PKData.lua:93-109` identifies the all-in condition using known non-folded hands and at most one remaining player with chips. Win odds use the hands and selected board prefix already in memory (`PKData.lua:866-893`). This is a concrete explanation for knowledge before an animation finishes. It does not prove knowledge while earlier betting decisions were still open.

`CSHoldem.proto:274-282` and `PKTable.lua:675-681` also establish a client acknowledgment after deal animation. Static code does not show how the server uses that acknowledgment. Its arrival must not independently override server hand-state and betting preconditions.

## Priority server audit surfaces

1. Snapshot redaction and recovery. `EnterRoomRSP`, `ChangeTableRSP`, and `GetRoomDataRSP` carry `TableStatus` and `PlayingStatus` (`CSGame.proto:180-251`). `SeatStatus.card1..card4` are annotated for showdown, and `TableStatus` also contains public cards and hand-history detail (`CSGameDef.proto:258-278,345-395`). `net_table.lua:3-36` reconstructs the client model. `BaseData.lua:13-44,426-440`, `PlayerData.lua:77-88`, and `PKData.lua:20-25` install received seat cards and boards without an independent showdown check. Audit the server's recipient, seat ownership, street, observer role, and snapshot consistency across reconnects and table changes. Server enforcement of the schema comment remains unverified.

2. Missing-card recovery. `GetCardsREQ` is empty, while its response contains board cards and two hole-card fields (`CSHoldem.proto:221-230`). The official caller sends it when the visible board count differs from 3, 4, or 5 for the current street or the player's cards are missing (`PKTable.lua:1117-1145`). The response replaces the board and updates the local player's cards (`net_pk.lua:170-175`), then refreshes the UI (`PKTable.lua:1109-1115`). There is no opponent UID or seat selector in this request schema. Audit stage filtering and authorized current-seat binding, including folded and observing sessions. Static existence of the request does not show that early calls disclose future cards.

3. Delayed cards-up observation. `RoomInfo` carries `open_observer`, `ob_delay_time`, and `src_roomid`, whose comment identifies a mirror room (`CSGameDef.proto:110-112`). Requests support observer entry and view changes (`CSGame.proto:168-177,220-232`). The UI intentionally flips all dealt hands in open-observer mode (`PKTable.lua:574-576`). `BaseData.lua:476-493` identifies observer and mirror-room state. `PKTable.lua:220-227` and `FriendsRoomOutlook.lua:3-13` display an initial waiting overlay. The shipped MTT text advertises a five-minute delay using `tpl_constdata.lua:103` and `tpl_mult_language.lua:18382`. These files do not verify actual server delay. Audit the entire delayed stream and all recovery, replay, table-change, and perspective-change responses against the same delayed timeline. UI waiting alone cannot keep received cards secret. Legitimate cards-up observation is a concrete alternative to cheating allegations based only on visible hands.

4. Replay and history authorization. `RecordDataModel.lua:421-434` fetches detail by `gameid` and language. `PKRecordData.lua:40-67,297-355,466-516` consumes recorded hole cards and boards and generates playback events. `PKRecordData.lua:138-145,538-548` explicitly runs a record model through the same handlers used by live play. `CSHoldem.proto:243-271` carries history cards, and `IngameHistory.lua:119-126` renders returned values directly. Audit server ownership, finished-hand availability, observer delay, and per-card redaction before serialization. Complete future playback data in a replay process is expected and does not demonstrate a live-hand leak. The request's `gameid` parameter alone does not establish an authorization defect.

## Other disclosure paths

Voluntary card sharing is explicit in `ShowMyCardREQ` and `ShowMyCardBRC` (`CSHoldem.proto:119-137`). `CSGameDef.proto:281-285,320-328` documents zero values for hidden cards and distinguishes showdown from voluntary disclosure. `net_pk.lua:125-138` installs the supplied hand-card array. Verify that non-disclosed positions are already zero or absent in server responses. Changing an eye icon is not a privacy boundary.

The embedded local `GameServer` knows both hands and a complete board, but the inspected creation call is guarded by `GuideManager:isInGuide()` (`LobbyByinDialog.lua:43-46`). It obtains scripted guide cards (`GameServer.lua:152-158`, `GameRoom.lua:170-185`). This is a tutorial simulator and supplies no evidence that production online dealing runs on a player's device.

APK bundle deobfuscation exposes client code and protocol definitions. The inspected online flow receives actual cards from network messages. Recovering source assets therefore does not itself recover a live server's undisclosed cards.

## Remediation and evidence needed

Recommended server invariant: serialize each card only when the authenticated recipient is entitled to that specific card at that hand stage and observer timeline. Apply the invariant before sending normal events, snapshots, recovery responses, and history. Keep the full deck server-side. Retain zero or absent hidden-card positions consistently. Exercise the same recipient and stage matrix across all these paths and verify that animation acknowledgments cannot skip betting preconditions. Client assertions can expose inconsistent responses during testing, but client filtering cannot restore secrecy once a value has arrived.

For a player report, preserve the exact game ID, room / table ID, UTC timestamp, client version, seat / account roles, whether cards-up spectating was enabled, and a full recording spanning the allegation and the subsequent reveal. Distinguish a prediction before betting closed from one during an all-in reveal effect. Save exact pre-reveal claims and several independent incidents. Do not infer packet contents from successful guesses or betting statistics alone.

To establish a leak, capture delivery timestamps and relevant card fields during authorized runtime testing, with the hand stage and recipient role recorded alongside them. A controlled hand using consenting accounts or an operator test environment permits the same conditions to be repeated. Public-table observations can document reported incidents within the agreed test scope. Compare ordinary seated, folded, reconnecting, and observer recipients at the same authoritative hand stage. A finding requires an unauthorized card in the received payload before the recipient's permitted disclosure time. Server logs should then identify the producer and authorization decision. Live authentication tokens and unrelated account data should remain excluded from research records.

## Status

This static audit is complete. Production exploitability, actual spectator delay, recipient filtering, and the reported opponent's method remain unverified. No live requests were made.
