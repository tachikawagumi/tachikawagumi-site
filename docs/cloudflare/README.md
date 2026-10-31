# Cloudflare Pages 手動管理

対象は太刀川組の既存Pagesプロジェクトです。サイト本体・DNS・独自ドメイン・301・フォーム・GA4は変更しません。GitHub履歴も書き換えません。現在は**読み取り調査を構築済み、削除は無効、承認済み対象は0件**です。API接続や過去デプロイ封鎖の成功を意味しません。

## 1. 代表者が登録するもの

Cloudflareへのログインは代表者の通常のChromeで行ってください。Workのブラウザで403となる操作の再試行は不要です。パスワード・トークン・認証コードをチャット、Issue、PR、ソースコードへ貼らないでください。

1. Cloudflareで対象アカウントのAccount IDをコピーします。過去ログのIDを推測して使用しません。
2. My Profile → API Tokens → Create Token → Custom tokenで、対象アカウントだけに限定した **Account / Cloudflare Pages / Read（API上はPages Read）** のトークンを作成します。最初はWriteやAccess、DNSの権限を付けません。有効期限を設定し、不要時に失効させてください。
3. GitHubリポジトリ → Settings → Secrets and variables → Actions → Secretsに `CLOUDFLARE_PAGES_READ_TOKEN` を登録します。値はCloudflareで発行したトークンです。
4. 同画面のVariablesに `CLOUDFLARE_ACCOUNT_ID` を登録します。`CLOUDFLARE_PAGES_PROJECT_NAME` は、この時点で正式名を管理画面から確認できれば登録できます。不明なら空のまま次へ進めます。
5. Actions → **Cloudflare Pages - read-only inventory** → Run workflow。ブランチは必ず`main`、modeは`discover`です。自動実行されません。
6. 成功したrunのArtifactsの`pages-read-only-…`を開き、`projects.json`から、連携先が`tachikawagumi/tachikawagumi-site`で、独自ドメインが`tachikawagumi.co.jp`のプロジェクトを選びます。リポジトリ名からプロジェクト名を決めないでください。該当が複数・不明なら停止して確認します。
7. 取得した正式な`name`をVariablesの `CLOUDFLARE_PAGES_PROJECT_NAME` に登録します。同じワークフローをmode=`inventory`で手動実行してください。設定した名称・GitHub連携・独自ドメインはコードでも再照合します。

Secretsを登録した後、名前だけを伝えてください。トークンの値は不要です。この機能に必要なGitHub権限は`contents: read`だけです。Cloudflare APIのPages権限は対象アカウント単位であり、同じアカウント内に別のPagesプロジェクトがある場合も権限が及ぶ点に注意してください。コード側は確認済みの1プロジェクトへ限定します。

## 2. 調査結果の読み方

`inventory.json`は全ページネーション取得後、各デプロイのID・URL・alias・環境・ブランチ・コミット・日時・stage/status・現在の本番・最新ブランチ判定・削除拒否理由と、9画像の匿名HTTP確認を記録します。API応答全体、env_vars、ビルド設定、コミットメッセージ、トークン、画像本体、GPS座標は保存しません。画像はメモリ内だけで検査します。GPSはEXIFのGPS IFDタグの有無だけを読み、位置データ自体はデコードしません。検出はExif GPSに限定され、XMP等すべての位置情報の不存在を保証するものではありません。

- `image_state: public`：HTTP200かつJPEG/WebPの内容を確認。PR #31の3枚はGPSの有無に関係なく掲載許可未確認写真として扱います。
- `not-found`：取得した全対象URLが404/410。未知のURLや外部保存コピーまで消去した意味ではありません。
- `unverified`：301/302、401/403、HTMLの200、通信失敗、サイズ上限、対象外ドメイン等を含みます。**封鎖成功と扱いません。** Accessのログインへの転送も、これだけで全経路の封鎖完了とはしません。
- `deletion_candidate: true`：現在のAPI情報で安全装置に該当しない「候補」です。削除承認ではありません。ブランチが不明・本番が確認不能・最新・稼働中・alias付きは削除しません。
- `additional_urls_unverified`：Pages以外のalias等。自動アクセス・変更せず追加対応として残します。

APIの生レスポンスや画像をデバッグ出力しないでください。Artifactsは公開リポジトリの閲覧可能性を前提に、必要情報のみ、保存期間7日です。GitHub Actionsでログの詳細デバッグを有効化しないでください。再実行時にmainが進んでいれば停止します。最新mainから新しい手動runを起動してください。

## 3. 削除の準備（承認前に実行しない）

調査とは別の **Cloudflare Pages - single approved deletion** を使用します。まずDeployment IDを**1個**入力し、mode=`dry-run`で実行します。Readトークンしか渡しません。`deletion.json`の`target`と`blockers`を代表者に提示してください。

削除候補ごとに、環境・ブランチ・コミット・日時・URLとalias・現在の本番/最新ではない根拠・問題画像のHTTP確認を示し、**代表者から対象IDを指定した削除承認を受けます。** 現時点では承認0件です。無条件の一括削除、`force`は実装していません。

承認後に限り、別PRで`deletion-approvals.json`へ次の形式を登録します。代表者が内容を確認してmainへ反映するのが第1段階です。`deployment`にはdry-runの`target`全体をそのままコピーします。架空のIDや日時を埋めないでください。

```json
{
  "account_id": "実際に確認したAccount ID",
  "project_name": "APIで確認した正式名",
  "approved_deployments": [
    {
      "deployment": {"dry-runのtarget全体": "説明用。実際の値へ置き換える"},
      "approved_by": "tachikawagumi",
      "approval_record": "代表者が当該IDを承認した記録への参照（秘密情報なし）",
      "approved_at": "実際の承認日時・UTC・ISO8601",
      "expires_at": "承認から7日以内の期限・UTC・ISO8601"
    }
  ]
}
```

代表者がGitHub Settings → Environmentsに **cloudflare-pages-delete** を用意します。利用可能ならRequired reviewersで代表者の承認を必須とし、Deployment branchesをmainだけに制限してください。利用できない場合も、**承認対象のPR確認→代表者自身によるID・承認ファイルハッシュ・確認文入力の手動実行**という二段階確認を必須とします。自動削除は有効化しません。Environmentsはワークフローに記述しただけでは承認ゲートが設定されたことになりません。

代表者の明示承認後、Readとは別の対象アカウント限定 **Pages Write** トークンを発行し、このEnvironmentのSecretに `CLOUDFLARE_PAGES_DELETE_TOKEN` を登録します。リポジトリ共通Secretには置かない運用です。このEnvironmentのVariable `CF_PAGES_DELETE_ENABLED` を明示的に`true`にするまで削除できません。承認済み一覧が空、期限切れ、別アカウント、別プロジェクト、別ID、状態変化、確認文不一致の場合も拒否します。

## 4. 承認済み1件の削除と検証

第2段階は代表者のGitHubアカウント`tachikawagumi`本人による手動実行です。次を入力します。

- Branch: `main`
- mode: `delete`
- deployment_id: 承認済みの1 ID
- approval_sha256: main上の`deletion-approvals.json`のSHA256（`sha256sum docs/cloudflare/deletion-approvals.json`で確認）
- confirmation: `DELETE:`に続けて同じID

削除前にAPIから対象・全デプロイ・現在の本番を再取得し、さらに直前にも取り直します。本番、ブランチ最新の試行、ブランチ最新の正常配信、alias付き、実行中は除外します。現在のサイトマップ15URL以上と共通CSS/JS・robots・旧pages.devの301/クエリ保持を確認し、異常時は削除しません。安全確認と削除APIの間を完全に原子的にはできないため、デプロイ進行中の作業は避けてください。`force`やDELETEの自動再試行はしません。

API成功を受けた時点で結果を記録し、一覧からの消失・対象画像URLの404/410・本番ID不変・既存公開URLと301を再確認します。失敗時も`deletion.json`を成果物に残します。API応答不明のタイムアウト等は、成功/失敗を推測せず新たな読み取り調査で確かめます。CDN反映待ち、Access転送、ネットワーク失敗は封鎖完了扱いにしません。必要に応じて時間を置いて再度inventoryを実行してください。

終了後は対象の承認エントリーを別PRで除去し、Environment変数を`false`に戻し、Writeトークンを失効させる運用です。画像URLの停止と問い合わせフォームの実送信は別問題です。フォームの無断実送信は行いません。

## 5. 削除拒否対象と残る作業

最新ブランチの問題画像をこのワークフローが勝手に更新・再デプロイすることはありません。候補を整理後に、次を比較して個別に承認・実装します。

| 手段 | 必要な確認・影響 |
| --- | --- |
| PagesのEnable access policy | 公式上はプレビュー保護。独自ドメインや本番pages.devは対象外。すべてのhash URL・branch alias・過去productionを未認証で別々に検証する |
| Cloudflare Access API | Pages Read/Writeでは設定しない。別途Access: Apps and Policies Read/Write権限、既存アプリ/ポリシー、Zero Trust組織、対象ホストを調査する。`tachikawagumi.co.jp`を対象に含めない。追加権限の付与は事前承認が必要 |
| 問題ブランチを安全な内容に更新 | GitHub PRとプレビュー成功を確認する。branch aliasは更新できても過去hash URLは残るので別途停止が必要 |
| aliasの停止・旧デプロイ削除 | 現行の本番/301に影響しないことを確認し対象ごとに承認。forceは別途設計・承認なしに追加しない |

今回のコードはAccessやプロジェクト、ドメイン、アカウント設定を変更しません。公開GitHubの旧コミットに残る画像も削除しません。Cloudflare側の閉鎖後、Git履歴、PR参照、キャッシュ、fork等の別の機微データ除去計画が必要です。全公開経路の閉鎖を確認するまで完全解決・評議会GOとは報告しません。

## 公式仕様と検証

- [Pages deployments一覧・ページネーション・Pages Read](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/list/)
- [Project一覧](https://developers.cloudflare.com/api/resources/pages/subresources/projects/methods/list/) / [Project取得・canonical_deployment](https://developers.cloudflare.com/api/resources/pages/subresources/projects/methods/get/)
- [Deployment削除・Pages Write・force](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/delete/)
- [Preview保護・alias・最新ブランチ削除不可](https://developers.cloudflare.com/pages/configuration/preview-deployments/)
- [GitHub Environmentsの承認設定](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)

オフラインの安全性試験：`python3 -m unittest discover -s tools/cloudflare -p 'test_*.py' -v`。外部通信・実削除なし。秘密の生レスポンスや画像を残すテストは作成しません。
