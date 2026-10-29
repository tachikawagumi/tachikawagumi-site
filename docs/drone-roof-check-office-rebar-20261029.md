# 自社事務所の配筋空撮写真：PR #26 組み込み記録

確認日：2026年10月29日。元ブランチHEAD：fa9e0bea94cce52d8df1d1e6dbc39cca99ee5f04。

## 受け渡しと変更

- ユーザー添付の tachikawagumi_drone_office_rebar_20261029.zip を受領。既存計画書の本人提供・自社事務所・掲載承認の記録と照合。
- WebP 2点を drone-roof-check/photos/ に追加。ZIPのSHA256、実寸775×675／600×523と一致。EXIF・GPS・XMPなしを確認。画像への追加加工はしていない。
- office-rebar セクションの仮コメントを、ZIPのfigure（alt・srcset・拡大リンク・キャプション）に置換。CSSは既存PRに追加済みなので重複追加していない。
- 自社事務所建て替え時の配筋撮影例として掲載。屋根点検の実績やAir 3Sでの撮影と断定せず、空撮による品質合格・寸法確認を保証しない説明を維持。
- 原本由来と画像ハッシュは drone-roof-check-office-rebar-photo-manifest.json に保存。

## 検証

- Chromeプレビューのiframe枠360／390／768／1280pxで横はみ出しなし。有効幅345／375／753／1265pxそれぞれでscrollWidthとclientWidthが一致。スマホ幅の写真・キャプション、PCの写真セクションを目視確認。実機検証ではない。
- 写真の読み込みとsrcset選択、拡大先WebPの存在・デコードを確認。ローカル画像・CSS・JS・内部リンク・アンカーの参照先が存在。
- ドローンページCTAから既存フォームへ遷移し、「工事について」の選択を確認。実際の送信なし。
- H1 1件、canonical、JSON-LD解析、robotsのDraft用noindex,nofollow維持、Googleタグ・共通問い合わせスクリプトが変更前と同一であることを確認。
- node tools/verify-contact-regression.cjs：合格。4種の問い合わせ選択、phone_click／contact_click、成功時のみgenerate_lead、失敗時0回、重複送信抑止。ネットワーク送信なし。
- 画像追加以外のトップ・工場ページ・既存実績・サイトマップ・共通CSS／JSは今回変更していない。

## 状態と未確認

- PR #26の作業ブランチだけを更新する。mainへマージ・本番公開は実施しない。Draftとnoindexは維持。
- 本番HTTP、Cloudflare Pagesプレビュー、スマホ実機、Search Console、GA4実集計、Core Web Vitalsは未確認。
- 既存PRに記載のサービス運用に関する未確認事項は今回の写真組み込みでは解消していない。公開前にnoindexを外し、改めて公開確認が必要。
