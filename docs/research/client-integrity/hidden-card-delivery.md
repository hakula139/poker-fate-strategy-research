# Hidden-card delivery

## Evidence and conclusion

The examined free-practice events are consistent with ordinary all-in and river showdown delivery. Two history responses repeat one completed hand and add no previously unseen card values. A `SitDownBRC` payload remains unexamined, and filtering in other rooms, recovery paths, and observer roles remains unverified. These findings leave the reported opponent's method unresolved.

Source citations refer to decoded files from the [Android 1.7.0 artifact](../../reference/artifacts/android-1.7.0.md). Its [artifact record](../../reference/artifacts/android-1.7.0.json) maps filenames to source locations and hashes.

## Practice-table runtime observations

The official client's free Hold'em practice sample contains 1,044 received packets: 641 decoded and 403 metadata-only. The decoded messages contain no unknown protobuf fields. Seat labels identify card owners, while authenticated recipient identity remains unverified.

| Message           | Finding                                                                                                                                                              |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HandCardRSP`     | 26 events each contain two cards and one owner-seat label.                                                                                                           |
| `RoundStartBRC`   | 68 events deliver incremental boards: no cards preflop, three on the flop, and one each on the turn and river.                                                       |
| `ShowHandRSP`     | Three events precede the remaining board after all-in actions and round closure. Four further events follow the river and round closure.                             |
| `GetHandsListRSP` | Both responses describe the same completed hand during the next hand. Only folded seat 4 has cards, matching its earlier `HandCardRSP`. Other rows omit card values. |

The history responses provide one example of card filtering. Outgoing requests were not recorded, and independently issued history queries remain unverified.

All metadata-only packets map to 24 known messages. One `SitDownBRC` contains a potential card container: `status` uses `SeatStatus`, which permits `card1..card4` (`CSGame.proto:327-330`, `CSGameDef.proto:258-279`). Its payload was discarded, so the card contents are unknown. The remaining schemas contain no explicit playing-card containers.

The sample excludes chip tables, controlled observer-role changes, reconnect recovery, and cross-account history access. The client hot update was not separately decoded.

## Transport and normal delivery

`Net.lua:64-102` decodes received packets, updates models, and then emits UI events. Card values are available in memory before their animations display them.

`HandCardRSP` carries hole cards and a seat ID (`CSHoldem.proto:17-38`). `PKData:updateSelfCard` uses the received seat ID when present (`net_pk.lua:28-35`, `PKData.lua:199-223`), allowing cards to belong to an observed seat. Recipient permissions must be established separately.

Public cards enter the model immediately and without street-based truncation (`net_pk.lua:64-75`, `PKData.lua:144-161`). The UI then selects the street animation (`PKTable.lua:610-710`). `ShowHandRSP` installs per-seat cards and clears fold flags before the UI reveals them (`CSHoldem.proto:84-96`, `net_pk.lua:96-113`, `PKTable.lua:1060-1079`). The server determines the permitted audience and delivery stage.

## Confirmed visual timing distinction

During an all-in effect, `PKTable.lua:665-678` hides the received river card behind a card back for 1.6 seconds. The effect applies when known non-folded hands leave at most one player with chips (`PKData.lua:93-109`). Win odds use cards already in memory (`PKData.lua:866-893`). This explains knowledge before the animation ends. Evidence of disclosure during an open betting decision would require a separate observation.

The client acknowledges deal completion (`CSHoldem.proto:274-282`, `PKTable.lua:675-681`). How the server uses that acknowledgment remains unverified.

## Priority server audit surfaces

1. **Snapshots and recovery.** `EnterRoomRSP`, `ChangeTableRSP`, and `GetRoomDataRSP` contain seat cards, boards, and history (`CSGame.proto:180-251`, `CSGameDef.proto:258-278,345-395`). Client handlers install those values without checking showdown state (`net_table.lua:3-36`, `BaseData.lua:13-44,426-440`, `PlayerData.lua:77-88`, `PKData.lua:20-25`). The schema annotates seat cards for showdown. Enforcement requires server-side recipient and stage filtering across reconnects and table changes.

2. **Missing-card recovery.** `GetCardsREQ` has no parameters. Its response carries a board and two hole cards (`CSHoldem.proto:221-230`). The client requests it for missing cards or a board count inconsistent with the street, then replaces its card state (`PKTable.lua:1109-1145`, `net_pk.lua:170-175`). Authorized seat binding and street filtering remain unverified.

3. **Cards-up observation.** Room fields support open observation, delay, and mirror rooms (`CSGameDef.proto:110-112`, `CSGame.proto:168-177,220-232`, `BaseData.lua:476-493`). Open-observer mode reveals dealt hands (`PKTable.lua:574-576`). The waiting overlay and advertised five-minute MTT delay establish intended behavior (`PKTable.lua:220-227`, `FriendsRoomOutlook.lua:3-13`, `tpl_constdata.lua:103`, `tpl_mult_language.lua:18382`). Actual delay requires consistent server filtering across the stream, recovery, replay, and view changes.

4. **Replay and history.** Replay detail is requested by `gameid` and language (`RecordDataModel.lua:421-434`). Recorded cards and boards pass through live-play handlers (`PKRecordData.lua:40-67,138-145,297-355,466-516,538-548`). History renders returned cards directly (`CSHoldem.proto:243-271`, `IngameHistory.lua:119-126`). Server checks must bind access to the recipient, completed-hand state, and observer delay before returning each card.

## Other disclosure paths

Voluntary sharing uses `ShowMyCardREQ` and `ShowMyCardBRC`. Hidden positions are represented by zero values (`CSHoldem.proto:119-137`, `CSGameDef.proto:281-285,320-328`, `net_pk.lua:125-138`). Those positions must be filtered before delivery.

The local tutorial `GameServer` knows both hands and the complete board. Its creation is guarded by `GuideManager:isInGuide()`, and its cards come from scripted guide data (`LobbyByinDialog.lua:43-46`, `GameServer.lua:152-158`, `GameRoom.lua:170-185`). The examined online path receives cards from server messages.

## Required privacy boundary

The server must serialize each card only for recipients entitled to it at the current hand stage and observer timeline. This rule applies to events, snapshots, recovery, and history. Animation acknowledgments must preserve betting preconditions, and hidden positions must remain zero or absent. Client filtering cannot restore secrecy after delivery.

A disclosure finding requires a received card whose recipient or hand stage makes it unauthorized. Seat roles, betting state, and permitted reveal state must accompany that evidence. The present sample leaves these wider server policies unresolved.
