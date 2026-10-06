# 株式会社 太刀川組 - 公式ウェブサイト

公式ウェブサイトです。土工・とび・コンクリート工事の専門企業としての情報を提供しています。

## プロジェクト情報

- **会社名**: 株式会社 太刀川組
- **代表者**: 太刀川 慶一
- **設立**: 昭和55年（創業40年以上）
- **事業内容**: とび・土工・コンクリート工事
- **住所**: 〒132-0035 東京都江戸川区新堀1-33-3
- **電話**: 03-3670-0534
- **メール**: tachikawa@nifty.com
- **対応エリア**: 関東一円

## ウェブサイト構成

### ページセクション

1. **ヘッダー・ナビゲーション**
   - 企業ロゴ（logo.png）
   - 企業名
   - ナビゲーションメニュー

2. **ヒーロー セクション**
   - 企業名表示
   - 「創業40年以上」のキャッチコピー
   - 事業内容の説明
   - CTA ボタン（電話・事業内容）

3. **事業内容セクション**
   - とび工事
   - 土工事
   - コンクリート工事
   - 建設補修

4. **会社概要セクション**
   - 企業情報
   - 企業理念
   - 詳細情報（会社名、代表者、設立年、事業内容、対応エリア）

5. **お問い合わせセクション**
   - 電話番号（クリック可能）
   - メールアドレス（クリック可能）
   - 営業時間

6. **アクセスセクション**
   - Google Maps 埋め込み
   - 住所情報

7. **フッター**
   - 企業情報
   - 連絡先
   - 営業時間
   - コピーライト

## ファイル構成

```
tachikawagumi-site/
├── index.html          # メインページ
├── style.css           # スタイルシート
├── script.js           # JavaScript
├── logo.png            # 企業ロゴ（オプション）
├── README.md           # このファイル
└── .gitignore          # Git 設定
```

## ローカル開発

### 必要環境
- ウェブブラウザ（Chrome, Firefox, Safari など）
- テキストエディタまたは IDE

### 実行方法

1. リポジトリをクローンします：
   ```bash
   git clone https://github.com/tachikawagumi/tachikawagumi-site.git
   cd tachikawagumi-site
   ```

2. `index.html` をブラウザで開きます：
   ```bash
   # macOS
   open index.html
   
   # Linux
   xdg-open index.html
   
   # Windows
   start index.html
   ```

3. または、ローカルサーバーを起動します：
   ```bash
   # Python 3
   python -m http.server 8000
   
   # Python 2
   python -m SimpleHTTPServer 8000
   
   # Node.js (http-server)
   npx http-server
   ```

   その後 `http://localhost:8000` にアクセスします。

## Cloudflare Pages でのデプロイ

### デプロイ手順

1. [Cloudflare Pages](https://pages.cloudflare.com/) にログインします

2. 「Create a project」をクリック

3. このリポジトリを選択

4. ビルド設定を以下のように設定します：
   - **フレームワーク**: なし（静的サイト）
   - **ビルドコマンド**: （空白）
   - **ビルド出力ディレクトリ**: `/` （または `.`）

5. 環境変数（不要）

6. 「Deploy」をクリック

### デプロイ後

- Cloudflare Pages が自動的にサイトをビルドしてデプロイします
- 各コミットごとにプレビュー URL が生成されます
- `main` ブランチへのプッシュで本番環境にデプロイされます

## ロゴについて

企業ロゴを使用するには：

1. ロゴファイル（PNG 形式）を `logo.png` として保存します
2. ファイルをリポジトリのルートディレクトリに配置します
3. HTML に自動的に読み込まれます

ロゴが見つからない場合、ヘッダーには企業名テキストのみが表示されます。

## カスタマイズ

### 色の変更

`style.css` で以下の色を変更できます：

- **プライマリカラー**: `#f39c12` （オレンジ）
- **ダークカラー**: `#2c3e50` （濃いグレー）

### 連絡先情報の更新

`index.html` で以下の情報を更新してください：

```html
<!-- 電話番号 -->
<a href="tel:03-3670-0534">03-3670-0534</a>

<!-- メールアドレス -->
<a href="mailto:tachikawa@nifty.com">tachikawa@nifty.com</a>
```

### Google Maps の埋め込みを更新

Google Maps Embed API の URL を生成：

1. [Google Maps Embed API](https://developers.google.com/maps/documentation/embed/get-started) にアクセス
2. 住所を検索して embed URL を取得
3. `index.html` の `<iframe src="..."` の URL を更新

## レスポンシブデザイン

サイトはモバイル、タブレット、デスクトップに対応しています：

- **モバイル**: 320px～
- **タブレット**: 768px～
- **デスクトップ**: 1200px～

## パフォーマンス

- 静的サイト（動的なバックエンドなし）
- 最小限の JavaScript
- CSS は最適化済み
- 画像は必要に応じて圧縮

## ブラウザ対応

- Chrome / Edge（最新版）
- Firefox（最新版）
- Safari（11+）
- モバイルブラウザ（iOS Safari, Chrome Mobile など）

## セキュリティ

- HTTPS デフォルト（Cloudflare Pages）
- XSS 対策実装
- メタデータは安全に設定

## ライセンス

© 2024 株式会社 太刀川組. All rights reserved.

## サポート

問題が発生した場合：

1. [GitHub Issues](https://github.com/tachikawagumi/tachikawagumi-site/issues) で報告してください
2. 電話でお問い合わせください: 03-3670-0534
3. メールでお問い合わせください: tachikawa@nifty.com

## 更新履歴

### v1.0.0 (2024-10-06)
- 初版リリース
- 企業情報表示機能
- モバイル対応
- Cloudflare Pages 対応