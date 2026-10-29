# 第18次改修：表示速度の再調査（公開前記録）

対象本番： https://tachikawagumi.co.jp/
基点main：`c249d19bd2bc8d47fb88c45aeb0045166b8aa782`。

## 同条件での本番再測定

Google PageSpeed InsightsのブラウザUIで測定。APIは今回使っていない。Lighthouse 13.5.0 / HeadlessChromium 153.0.8010.36。スマホはMoto G Powerエミュレーション、低速4G、初回読み込み、1ページのみのセッション。PCはデスクトップエミュレーション、カスタムスロットリング。PSIの初回読み込み条件を使用し、実行側のキャッシュを独自に操作していない。

時刻は2026-10-29 JSTのレポート作成時刻。以下は第18次のコードを公開する前の、同一mainに対するラボ値であり、実ユーザーのCore Web Vitalsではない。

|作成時刻|環境|Performance|Accessibility|Best Practices|SEO|FCP|LCP|TBT|CLS|Speed Index|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|01:10:01|スマホ1|82|100|100|100|1.7s|4.4s|120ms|0|2.7s|
|01:13:03|スマホ2|77|100|100|100|1.7s|4.5s|280ms|0|2.8s|
|01:13:59|スマホ3|84|100|100|100|1.7s|4.4s|10ms|0|1.7s|
|01:13:59|PC|97|100|100|100|0.5s|1.2s|30ms|0|1.0s|

スマホ中央値は82点・LCP約4.4s。第17次公開後の86・78・92点と条件表記は同じだが時刻が異なるため、差をコード変更の効果や悪化と断定しない。独立した監査の値も、端末・CPU・ネットワーク・測定時刻・キャッシュ条件が異なれば変わり得る。スマホ90点の安定達成とLCP2.5s以下は未達。

- 1: https://pagespeed.web.dev/analysis/https-tachikawagumi-co-jp/dx7xq8t3qs?form_factor=mobile
- 2: https://pagespeed.web.dev/analysis/https-tachikawagumi-co-jp/kvezspozow?form_factor=mobile
- 3: https://pagespeed.web.dev/analysis/https-tachikawagumi-co-jp/34yt9yum0r?form_factor=mobile
- PC: https://pagespeed.web.dev/analysis/https-tachikawagumi-co-jp/34yt9yum0r?form_factor=desktop

2回目は最初にレポートへ移動した時点で結果の読み込み中だったため、同じレポートURLを開いて完了後の値を取得した。3回目も同じレポートを再読み込みして結果を取得した。結果未取得を測定済みとは扱わず、良いスコアだけを採用しない。

## LCP・JavaScriptの切り分け

2回目のスマホで、LCPは `assets/optimized/tobi-mobile.avif`。LCP内訳画面の表示値は次のとおり。

|内訳|表示値|
|---|---:|
|Time to First Byte|0ms|
|リソース読み込み遅延|150ms|
|リソース読み込み時間|90ms|
|要素レンダリング遅延|1,190ms|

この内訳はトレース側の値で、上表のスロットリング後LCP4.5sと同じ尺度で足し合わせない。0msという表示から、ネットワーク・接続時間を含む実際のTTFBが常に0であるとは判断しない。

同じレポートの長時間タスク監査には、既存 `gtag.js?id=G-0YE8VVH5FC` の243ms・135ms（計378ms）、自社ページの172ms・59ms、帰属不可79msが表示された。JavaScript負荷は残るが、各タスクの継続時間の合計をTBTと同一視しない。これだけでGA4がレンダリング遅延の全原因と断定することもできない。

ヒーロー写真そのものにはopacity/transformアニメーションがなく、コピー部分のreveal演出は既存の実装。今回これらを無条件に削除していない。画像配信の削減余地はPSI推定168KiB、未使用JavaScriptは推定74KiB。これらの推定容量を、そのまま初回転送量や改善済み容量とは呼ばない。

## HTTPの接続時間を別計測

同じクラウド実行環境からcurlで新規プロセスのGETを3回実行。URLは本番トップ、HTTP200、キャッシュバスターなし、独自の帯域・CPU制限なし、TLS検証は標準のまま。これはPSIの低速4G条件とは異なる。

|回|TLS確立まで（time_appconnect）|先頭バイトまで（time_starttransfer）|全体（time_total）|
|---|---:|---:|---:|
|1|5.286s|5.514s|5.514s|
|2|5.513s|5.665s|5.708s|
|3|5.399s|5.917s|5.918s|

この計測では接続・TLS確立の時間が大きい。time_starttransferをサイトのサーバー処理時間そのものと断定しない。PSIのTTFB内訳表示との条件差を残し、TTFBの主因の特定は未完了とする。

## 第17次最適化の保護

- 本PRはトップのhead、preload、pictureのAVIF/WebP切り替え、既存CSS・全JavaScriptを変更しない。
- 元写真・最適化済み画像のファイルを変更・追加・削除しない。新しい実績一覧も既存のGPSを含まないWebPを参照する。
- 第17次ではローカル検証でスマホAVIF1件、PCで選択WebP1件、AVIF未対応MIMEの模擬時に既存WebP1件を確認済み。今回もプレビューでメディア条件・画像表示を回帰確認する。
- GA4・Formspree・リダイレクト・キャッシュ設定を点数のために変更しない。計測開始を利用者の操作待ちにする等の変更も行わない。

## 別PRで検討する速度改善案（今回は未実装）

1. 同じ端末・CPU・回線条件のPerformanceトレースで、LCPのデコード/描画とJavaScriptのタスクを照合し、レンダリング遅延の寄与を確認する。
2. preload対象の選択と重複取得を確認したうえで、画像の別形式・サイズや合成処理の変更を小さく比較する。目視で画質を保てない案は採用しない。
3. GA4を変更する案は、最初のpage_view・短時間訪問・既存3イベント・工事種別の維持を別途検証する。未検証の遅延読み込みを本PRへ混在させない。
4. 接続時間とTTFBを条件を揃えて再調査する。キャッシュの長期化は更新反映との整合が必要で、既存の非ハッシュ資産に一律immutableを付けることはしない。

本PRの実績一覧・相談案内・見出し修正をもって、速度目標を達成したとは報告しない。INP/CrUX、実スマートフォンのCPU・ソフトキーボード、実Safariの測定は未検証。

## 新設実績一覧のプレビュー計測

初回プレビュー ecaf527（2026-10-29 01:43:54 JST）：スマホ Performance 80、Accessibility 100、Best Practices 100、SEO 69、FCP 2.5秒、LCP 3.9秒、TBT 160ms、CLS 0、Speed Index 4.7秒。
https://pagespeed.web.dev/analysis/https-7676d9d9-tachikawagumi-site-pages-dev-works/7r2m9g529q?form_factor=mobile

画像監査で、縦長の足場写真が1350px版を取得していることを確認。高さ230px・object-fit:containに合わせ、新設一覧の縦長画像だけsizesを130pxまたは173pxに修正。既存540px／720px版を使用でき、元写真・圧縮品質は変更しない。SEOはPagesプレビューのnoindexを含むため、本番SEO評価とは区別する。

## 表示・回帰確認

- メッシュフェンスH1：変更前1280pxで末尾「事」が単独行になる現象を再現。語句単位の2行構成に修正し、390／768／1024／1280pxで確認。
- 同意エラー：360×640と390×840のブラウザ幅で画面内に表示され、チェック欄へフォーカス。画面外になる指摘は再現せず、フォーム処理は変更しない。実機・ソフトキーボードは未確認。
- ローカルの通信モックで未入力・不正メール・未同意は送信不可、失敗時入力保持、再試行、二重送信防止、成功時リセット・成功表示クリアを確認。成功時だけgenerate_leadが1回、失敗時0回。実送信なし。
- 工場／遮音壁から問い合わせ種別を引き継ぎ。中央・ヘッダー問い合わせのcontact_clickを個別に1回確認。phone_clickはコード維持を確認し、発信操作は実施しない。
- トップのhead・全script・form・既存ギャラリーの画像リンクはmainと同一。施工写真・計測ID・エンドポイント・SEO・転送設定は変更なし。
