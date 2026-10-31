# 過去デプロイ整理：承認前の準備

## 現在の状態

この変更は専用PRでのレビュー用です。mainへのマージ、Cloudflare APIの実照合、削除、Access設定変更はまだ実施していません。
`cleanup-approval.json`は`enabled: false`、承認ID一覧は空です。このPRのマージ承認と削除実行承認は別です。
既存のinventory・単件削除ワークフローとその安全装置は変更せず、共通API処理を再利用する手動ワークフローを追加します。

| 分類 | 件数 | 位置づけ |
|---|---:|---|
| 固定削除候補 | 177 | 過去production 78 / preview 99。全件aliasなし。未承認 |
| 別対処の過去preview | 41 | ブランチ最新・最新成功・alias付き。削除しない |
| 現行本番 | 1 | 絶対保護 |
| 既に手動削除・URL閉鎖確認済み | 1 | 今回の候補・API期待一覧から除外 |

全ID・URL・ブランチ・alias・保護理由は[cleanup-candidates.md](cleanup-candidates.md)、コミット・日時・状態を含む機械用固定データは[cleanup-plan.json](cleanup-plan.json)です。
既存inventory #4（run `41179402871`）のサニタイズ済みメタデータを再利用し、全画像の再調査は行いません。元inventoryのSHA256はplanの`source.inventory_sha256`へ記録しました。

絶対に削除しない指定ID：

- 現行本番 `b9f89a1f-cffa-427a-800d-98280178678a`
- 明示保護 `a0244d88-1233-478b-8c1d-cc031c227862`
- 試験削除済み `55ffe624-3398-4f08-9f8e-7441924fc90a`（再試行もしない）

## 第1段階：PRレビューと読み取り専用の実照合

1. 代表者がこのPRのコード・固定一覧をレビューし、**準備機能のmain反映だけ**を別途承認します。Workは無断マージしません。
2. 将来マージする場合も、マージコミットのタイトルを`[CF-Pages-Skip]`で始めます。このPRのブランチコミットにも同じprefixを付けます。管理ファイルだけの変更で本番IDが変わるのを避けるためです。ドメイン・ビルド設定自体は変更しません。prefixの有無にかかわらず本番IDが変われば処理は停止します。
3. main反映後、代表者がActions → **Cloudflare Pages - frozen cleanup** → Run workflow → branch=`main`、mode=`preflight`を実行します。既存のRead SecretとAccount ID/Project Variablesを使います。Write Secretは渡しません。
4. Artifactsの`pages-cleanup-preflight-.../cleanup-preflight.json`を取得し、現行本番ID、177件の現在の残数、42件の保護対象、欠落ID、plan/state/account SHA256を確認します。Account IDそのもの・API生レスポンス・画像・GPS座標は出力しません。

APIは正式プロジェクト`tachikawagumi-site`のGETに限定します。GitHub連携先と独自ドメインも既存コードで検証し、ページネーション取得を2回照合します。PALカリなど他プロジェクトを列挙しません。

新しいID、現行本番IDの変化、保護対象の欠落、branch/alias/コミット/日時/stage/status/URLの変化、候補が最新になった場合は停止します。既存候補が欠落していれば報告できますが、削除成功・URL閉鎖成功と断定しません。欠落IDを削除対象に追加したり、黙って再試行したりしません。

このワークフローは信頼済みmain限定です。現時点では未マージなので、PRブランチからAPI照合を強行せず、実照合は未確認として扱います。

## 第2段階：実照合後に削除対象を承認

1. preflightの結果に基づき、最初は5件程度、以後は**1回最大25件**の対象IDを固定して代表者に提示します。177件を無条件で全件削除する機能ではありません。
2. 代表者が具体的なIDと影響範囲を承認した後に限り、別PRで`cleanup-approval.json`を埋めます。今回のPRでは空・無効のままです。
3. 承認ファイルには、次を記録します。
   - `enabled: true`、`approved_by: tachikawagumi`、承認記録、実際の承認日時、7日以内の期限
   - preflightの`plan_sha256`・`account_sha256`・`state_sha256`・`run_id`（`preflight_run_id`へ）・`expected_absent_ids`
   - 承認された対象だけの`authorized_ids`、同じ件数の`max_deletions`（1〜25）
4. この承認PRも代表者の承認後にのみmainへ反映します。マージタイトルの`[CF-Pages-Skip]`が必要です。mainへ承認ファイルを置くだけでは削除されません。
5. `cloudflare-pages-delete` Environmentはmain限定とし、利用可能ならRequired reviewersで代表者承認を必須にします。設定済みかどうかは現時点で未確認です。利用できない場合も「具体的な承認PRの確認 → 代表者本人によるハッシュ・件数の手動入力」の二段階を維持します。
6. 別のPages WriteトークンをそのEnvironmentの`CLOUDFLARE_PAGES_DELETE_TOKEN`に登録し、Environment Variable `CF_PAGES_DELETE_ENABLED=true`を設定します。Read Tokenを流用しません。トークンの発行・登録は代表者が行い、値をチャットやコミットへ貼りません。

## 第3段階：承認された範囲だけを順次実行

代表者本人がActionsで次を指定します。

- Workflow: **Cloudflare Pages - frozen cleanup**
- Branch: `main`
- Mode: `delete`
- `approval_sha256`: main上の承認ファイルの正確なSHA256
- `confirmation`: `DELETE:<そのSHA256>:<承認された正確な件数>`

実行者と再実行者は両方`tachikawagumi`である必要があります。手動実行のみ、GitHub権限`contents: read`、固定SHAのActions、共通concurrencyで重複実行を抑止します。PR/push/scheduleトリガーやDELETEのmatrix並列実行はありません。

各1件について、mainのSHA・承認の有効期限とファイルハッシュ・本番ID・全デプロイの固定状態・候補の最新/alias有無を再照合します。本番15URL以上、sitemap、robots、共通CSS/JS、既存301とクエリ保持を確認した後、もう一度API状態と対象詳細を取得してからDELETEを1回だけ送ります。`force`はAPIルートで拒否します。

削除後はAPIから対象が消えたこと・残りの全固定メタデータと本番IDが変わっていないこと・対象トップと9画像がすべて404/410であること・本番HTTPと301を確認します。フォームへの実送信やGA4集計は自動テストの対象に含めません。これらを「正常確認済み」とは報告しません。

APIがタイムアウトした場合、削除が成立した可能性があるため自動再試行しません。送信直前からサニタイズ済みのattempt記録を残します。API成功と公開停止確認成功を分け、200 HTML、認証転送、403、通信失敗を閉鎖成功と扱いません。読み戻しが失敗しても独立した本番HTTP確認を試みます。

途中停止やrunnerタイムアウトの後は同じrunを安易に再実行しません。新しいpreflightで欠落IDとURL閉鎖を確認し、残りだけの新しい承認ファイルを用意します。既に消えたIDを黙ってスキップする自動再開は実装しません。

## 41件の公開停止策（調査のみ）

41件はすべて過去previewのブランチ最新・最新成功・alias付きです。`a0244d88-...`も含み、今回の削除候補から外しています。

| 方法 | 評価と制限 |
|---|---|
| PagesのEnable access policy | 第一候補。プレビュー認証保護。実設定・既存Accessアプリ・料金/利用可否は未確認。独自ドメインとapex pages.devを対象に入れない |
| AccessのAPI設定 | 将来の別作業。Accessアプリ/ポリシーの追加権限と既存ルール調査が必要。今回のPages Read/Write機能へ混在させない |
| aliasだけを止める | 不十分。古いhash URLが独立して残るため、両方を検証する必要がある |
| 安全なブランチ更新 | 旧最新版を古いデプロイにできる可能性があるが、新しいデプロイも作る。全41ブランチの安全な公開物を用意し、旧hashの削除可否を実APIで検証する別承認が必要。今回は実施しない |
| forceでalias付き削除 | 公式APIのforceは非productionのactive alias向け。ブランチ最新版削除の制限を解消した根拠にはならない。今回は禁止 |
| GitHubブランチ削除・Pagesプロジェクト削除 | 過去hash公開停止の代わりとしない。今回の作業対象外 |

Access設定を将来承認された場合は、既存アプリとポリシーを必要最小限のRead権限で先に取得し、対象を`*.tachikawagumi-site.pages.dev`のプレビュー範囲へ限定します。Pages組み込み設定で作られる実際の対象範囲を確認し、独自ドメイン`tachikawagumi.co.jp`と`tachikawagumi-site.pages.dev`を含めません。
41件のhash URLと全branch aliasについてトップ・9画像をCookieも認証ヘッダーもない状態で再確認し、ログインへの302だけで完了と判断せず、リダイレクト先・設定範囲・画像内容を取得できないことを照合します。古いproductionのhash URLをAccessが一律保護すると仮定しません。

Access APIのアプリ/ポリシー変更は`Access: Apps and Policies Write`が必要です。現在のRead/Write Pagesトークンでは代用せず、対象アカウント限定の別権限を将来の明示承認後に用意します。既存Accessルールを上書きしたり本番を認証必須にする実装はありません。

公式根拠：

- [Preview deployments / Access / branch alias / 最新版削除制限](https://developers.cloudflare.com/pages/configuration/preview-deployments/)
- [Pages deployment DELETE / Pages Write / force](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/delete/)
- [GitHub integration / commit prefixによるbuild skip](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/)
- [Access policy API / 追加権限](https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/applications/subresources/policies/methods/create/)

## 残る確認事項

- 最新APIとの照合と現在の本番ID・alias状態（未実行）
- EnvironmentのRequired reviewers、main制限、Write Secret・enable変数の設定状態（未確認）
- 41件のAccess設定と全経路の保護可否（未変更・未検証）
- 全過去デプロイの公開停止（今回の準備では未完了）
- 公開GitHub旧履歴の画像、外部キャッシュ・保存コピー（今回処理しない）
- Search Console・GA4実集計・Core Web Vitals（今回未確認）

GitHub履歴は書き換えず、サイト・フォーム・GA4・SEO・デザイン・DNS・301設定は変更しません。PALカリはAPIルート段階でも対象外です。
