-- Active: 1742188538057@@tech0-techbrain-sql.mysql.database.azure.com@3306
-- データベースを作成
CREATE DATABASE IF NOT EXISTS step4_team3_db;

-- 作成したデータベースを使用
USE step4_team3_db;

-- ユーザー管理関連のテーブル群 --

-- Users（ユーザーテーブル）
-- ユーザーの基本情報を管理するテーブル
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,    -- ユーザーを識別するID（自動採番）
    email VARCHAR(255) NOT NULL UNIQUE,        -- ログイン用メールアドレス（重複不可）
    password_hash VARCHAR(255) NOT NULL,       -- 暗号化されたパスワード
    username VARCHAR(100) NOT NULL,            -- 表示名
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- アカウント作成日時
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 更新日時
    INDEX idx_email (email)                    -- メールアドレスでの検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- FamilyGroups（家族グループテーブル）
-- 家族単位でのグループを管理するテーブル
CREATE TABLE family_groups (
    group_id INT PRIMARY KEY AUTO_INCREMENT,   -- グループを識別するID（自動採番）
    group_name VARCHAR(100) NOT NULL,          -- グループ名（例：「田中家」）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- グループ作成日時
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- UserFamilyGroups（ユーザーと家族グループの中間テーブル）
-- ユーザーとグループの多対多の関係を管理するテーブル
CREATE TABLE user_family_groups (
    user_id INT,                               -- どのユーザーか（外部キー）
    group_id INT,                              -- どのグループか（外部キー）
    role ENUM('poster', 'viewer') NOT NULL,    -- ユーザーの役割（投稿者/閲覧者）
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- グループ参加日時
    PRIMARY KEY (user_id, group_id),           -- 複合主キー
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES family_groups(group_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 物品カテゴリーと参照データのテーブル群 --

-- Categories（カテゴリーマスターテーブル）
-- 物品のカテゴリー階層を管理するテーブル
CREATE TABLE categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,    -- カテゴリーを識別するID
    category_name VARCHAR(100) NOT NULL,           -- カテゴリー名
    parent_category_id INT,                        -- 親カテゴリーID（階層構造用）
    FOREIGN KEY (parent_category_id) REFERENCES categories(category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ReferenceItems（参照用物品マスターテーブル）
-- 市場価格参照用の標準的な物品情報を管理するテーブル
CREATE TABLE reference_items (
    ref_item_id INT PRIMARY KEY AUTO_INCREMENT,    -- 参照用物品ID
    category_id INT NOT NULL,                      -- カテゴリーID
    item_name VARCHAR(255) NOT NULL,               -- 物品名
    brand_name VARCHAR(255),                       -- ブランド名
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- データ作成日時
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    INDEX idx_item_name (item_name),              -- 物品名での検索を高速化
    INDEX idx_category (category_id)               -- カテゴリーでの検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ReferenceMarketItems（参照用メルカリ出品データテーブル）
-- メルカリの出品データを参照するためのテーブル
CREATE TABLE reference_market_items (
    market_item_id INT PRIMARY KEY AUTO_INCREMENT,    -- 出品データID
    ref_item_id INT NOT NULL,                         -- 参照用物品ID
    market_price DECIMAL(10,2) NOT NULL,              -- 出品価格
    condition_rank ENUM('S', 'A', 'B', 'C', 'D'),    -- 商品状態
    listing_date DATE NOT NULL,                       -- 出品日
    status ENUM('active', 'sold', 'removed'),         -- 出品状態
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,    -- データ作成日時
    FOREIGN KEY (ref_item_id) REFERENCES reference_items(ref_item_id),
    INDEX idx_ref_listing (ref_item_id, listing_date) -- 参照物品と出品日での検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 物品管理関連のテーブル群 --

-- Items（物品テーブル）
-- ユーザーが登録した物品の基本情報を管理するテーブル
CREATE TABLE items (
    item_id INT PRIMARY KEY AUTO_INCREMENT,        -- 物品を識別するID
    user_id INT NOT NULL,                          -- 登録したユーザーID
    group_id INT NOT NULL,                         -- 所属する家族グループID
    ref_item_id INT,                               -- 参照用物品ID（価格参照用）
    category_id INT,                               -- カテゴリーID
    item_name VARCHAR(255) NOT NULL,               -- 物品名
    description TEXT,                              -- 物品の説明
    condition_rank ENUM('S', 'A', 'B', 'C', 'D'), -- 物品の状態ランク
    status ENUM('active', 'archived') DEFAULT 'active',  -- 物品の状態（現役/整理済み）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- 登録日時
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 更新日時
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES family_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (ref_item_id) REFERENCES reference_items(ref_item_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    INDEX idx_user (user_id),                      -- ユーザーIDでの検索を高速化
    INDEX idx_group (group_id)                     -- グループIDでの検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ItemImages（物品画像テーブル）
-- 物品の画像データを管理するテーブル
CREATE TABLE item_images (
    image_id INT PRIMARY KEY AUTO_INCREMENT,       -- 画像を識別するID
    item_id INT NOT NULL,                          -- 物品ID
    image BLOB,                                    -- 画像データ
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- アップロード日時
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    INDEX idx_item (item_id)                       -- 物品IDでの検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- コミュニケーション関連のテーブル群 --

-- Threads（スレッドテーブル）
-- 物品に関する討論スレッドを管理するテーブル
CREATE TABLE threads (
    thread_id INT PRIMARY KEY AUTO_INCREMENT,      -- スレッドを識別するID
    item_id INT NOT NULL,                          -- 対象物品ID
    title VARCHAR(255),                            -- スレッドのタイトル
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- 作成日時
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 更新日時
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    INDEX idx_item (item_id)                       -- 物品IDでの検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Messages（メッセージテーブル）
-- スレッド内のメッセージを管理するテーブル
CREATE TABLE messages (
    message_id INT PRIMARY KEY AUTO_INCREMENT,     -- メッセージを識別するID
    thread_id INT NOT NULL,                        -- 所属スレッドID
    user_id INT NOT NULL,                          -- 投稿者ID
    parent_message_id INT,                         -- 返信先メッセージID（スレッド形式用）
    content TEXT NOT NULL,                         -- メッセージ内容
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- 作成日時
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- 更新日時
    is_edited BOOLEAN DEFAULT FALSE,               -- 編集済みフラグ
    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_message_id) REFERENCES messages(message_id),
    INDEX idx_thread (thread_id),                  -- スレッドIDでの検索を高速化
    INDEX idx_parent (parent_message_id)           -- 親メッセージIDでの検索を高速化
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- MessageReactions（メッセージリアクションテーブル）
-- メッセージへのリアクション（いいね等）を管理するテーブル
CREATE TABLE message_reactions (
    reaction_id INT PRIMARY KEY AUTO_INCREMENT,    -- リアクションを識別するID
    message_id INT NOT NULL,                       -- 対象メッセージID
    user_id INT NOT NULL,                          -- リアクションしたユーザーID
    reaction_type ENUM('like', 'heart', 'smile', 'sad', 'agree') NOT NULL,  -- リアクションの種類
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- リアクション日時
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_reaction (message_id, user_id, reaction_type)  -- 同一ユーザーからの重複リアクションを防止
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- MessageAttachments（メッセージ添付画像テーブル）
-- メッセージに添付された画像を管理するテーブル
CREATE TABLE message_attachments (
    attachment_id INT PRIMARY KEY AUTO_INCREMENT,  -- 添付を識別するID
    message_id INT NOT NULL,                       -- 対象メッセージID
    image BLOB,                                    -- 画像データ
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- アップロード日時
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;