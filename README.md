# 株式会社太刀川組｜公式ホームページ

**公式サイト：<https://tachikawagumi.co.jp/>**

株式会社太刀川組（東京都江戸川区）の公式ホームページを管理する公開GitHubリポジトリです。  
**工事のご相談・お見積もり・お問い合わせは、[公式サイト](https://tachikawagumi.co.jp/#contact)からお願いします。** このGitHubリポジトリはお問い合わせ窓口ではありません。

## 会社・サイトについて

- **会社名：** 株式会社太刀川組
- **創業：** 昭和55年（1980年）
- **所在地：** 東京都江戸川区新堀1-33-3
- **電話：** 03-3670-0534
- **主な工事：** とび・土工・コンクリート工事、工場改修・補修、高速道路・遮音壁関連工事など
- **建設業許可：** 東京都知事許可（般－7）第58800号／とび・土工工事業
- **主なご相談エリア：** 東京・千葉・埼玉南部・川崎周辺（現場条件等を確認のうえご案内）

掲載内容・施工範囲・許可情報などの詳細は、必ず公式サイトの最新の案内をご確認ください。

## 公開ページ

| 内容 | 公式URL |
| --- | --- |
| トップ・会社案内・お問い合わせ | https://tachikawagumi.co.jp/ |
| 工場改修・補修 | https://tachikawagumi.co.jp/factory-renovation/ |
| 高速道路・遮音壁 | https://tachikawagumi.co.jp/sound-barrier/ |
| 施工実績一覧 | https://tachikawagumi.co.jp/works/ |
| メッシュフェンス一時撤去・復旧 | https://tachikawagumi.co.jp/works/mesh-fence-restoration/ |
| アドフラット仮囲い | https://tachikawagumi.co.jp/works/adflat-temporary-enclosure/ |
| フェンス部分改修 | https://tachikawagumi.co.jp/works/fence-panel-renovation/ |
| ドローンによる屋根・高所の現況確認 | https://tachikawagumi.co.jp/drone-roof-check/ |
| プライバシーポリシー | https://tachikawagumi.co.jp/privacy/ |

ドローンページは**撮影による外観・現況確認の相談窓口**です。撮影だけで構造・劣化状態・安全性などの専門的な診断が確定するものではありません。

## サイトの構成と運用

- HTML・CSS・JavaScriptを中心とした静的サイトです。WordPress等のCMSを前提としません。
- GitHubの `main` ブランチを管理し、Cloudflare Pages（プロジェクト名：`tachikawagumi-site`）で公開しています。
- 公式ドメインは `tachikawagumi.co.jp` です。
- 主要ファイル：
  - `index.html` — トップページ
  - `factory-renovation/`、`sound-barrier/`、`works/`、`drone-roof-check/`、`privacy/` — 下層ページ
  - `style.css`、`styles.css`、`script.js`、`assets/` — 表示・操作・画像など
  - `sitemap.xml`、`robots.txt`、`404.html` — 検索エンジン向け設定・404ページ
- お問い合わせフォーム、アクセス解析、内部リンクなどは公式サイト側の実装を参照してください。

### 公開時の確認

1. GitHubの `main` へのマージだけで公開完了と判断せず、**Cloudflare Pagesのデプロイ成功**を確認する。
2. 公式ドメインで、対象ページが正常に開くこと、写真・内部リンクが表示できることを確認する。
3. `sitemap.xml`、`robots.txt`、問い合わせ導線など、関連箇所への影響を確認する。
4. 問い合わせフォームの実送信は、必要な場合に適切な手順で実施する。

## 写真と情報の取り扱い

施工写真は掲載権利・プライバシー・撮影情報を確認して取り扱います。自社の担当範囲と他社の施工部分を混同せず、AI生成の比較イメージを掲載する場合は実際の施工写真と区別して表示します。

---

**公式ホームページ：** <https://tachikawagumi.co.jp/>  
**工事のご相談：** <https://tachikawagumi.co.jp/#contact>
