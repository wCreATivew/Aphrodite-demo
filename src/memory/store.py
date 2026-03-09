# -*- coding: utf-8 -*-
"""
记忆存储核心类

功能：
- SQLite 存储（文本 + 元数据）
- FAISS 向量索引（语义检索）
- 标签权重打分（关键词匹配）
- 遗忘曲线 + 强化机制
- 话题熔断
"""
from __future__ import annotations

import os
import re
import json
import time
import math
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import numpy as np

from .schemas import (
    MemoryConfig,
    MemoryTag,
    EpisodicMemory,
    SemanticMemory,
    WorkingMemory,
    TopicBreakerState,
    memory_weight,
    recency_score,
)

# FAISS 导入
try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False
    print("[Memory] 警告：FAISS 未安装，语义检索功能不可用")

# SentenceTransformer 导入
try:
    from sentence_transformers import SentenceTransformer
    EMBED_AVAILABLE = True
except Exception:
    EMBED_AVAILABLE = False
    print("[Memory] 警告：sentence-transformers 未安装，嵌入功能不可用")


class MemoryStore:
    """
    记忆存储核心类
    
    使用方式：
    1. 初始化
       store = MemoryStore(character_id="char_001", db_path="memory/char_001.sqlite")
    
    2. 写入记忆
       store.add("用户喜欢咖啡", memory_type="episodic", emotion="happy")
    
    3. 检索记忆
       memories = store.retrieve("用户喜欢喝什么", k=5)
    
    4. 定期巩固（提炼语义记忆）
       store.consolidate()
    """
    
    def __init__(
        self,
        character_id: str = "default",
        db_path: str = "memory.sqlite",
        index_path: str = "memory.faiss",
        ids_path: str = "memory_ids.npy",
        model_name: str = "BAAI/bge-small-zh-v1.5",
        config: Optional[MemoryConfig] = None,
    ):
        """
        初始化记忆存储
        
        Args:
            character_id: 角色 ID（多角色隔离）
            db_path: SQLite 数据库路径
            index_path: FAISS 索引路径
            ids_path: FAISS ID 映射路径
            model_name: 嵌入模型名称
            config: 记忆配置（可选，默认使用通用配置）
        """
        self.character_id = character_id
        self.config = config or MemoryConfig()
        
        # 数据库路径
        self.db_path = db_path
        self.index_path = index_path
        self.ids_path = ids_path
        
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        
        # 初始化数据库
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=30000;")
        self._db_lock = threading.RLock()
        self._init_tables()
        
        # 初始化向量索引
        self.index = None
        self.id_map: List[int] = []  # FAISS 索引 → SQLite ID
        self.model = None
        
        if FAISS_AVAILABLE and EMBED_AVAILABLE:
            self._init_embedding(model_name)
            self._load_or_rebuild_index()
        
        # 标签缓存（memory_id -> [(phrase, weight), ...]）
        self.tag_cache: Dict[int, List[Tuple[str, float]]] = {}
        self._load_tags_cache()
        
        # 话题熔断状态
        self.breaker_state = TopicBreakerState()
        
        # 工作记忆
        self.working_memory = WorkingMemory(character_id=character_id)
        
        print(f"[Memory] 记忆存储已初始化：{self.character_id}")
        print(f"[Memory] 当前记忆数：{self.count()}")
    
    def _init_tables(self):
        """初始化数据库表"""
        with self._db_lock:
            cur = self.conn.cursor()
            
            # 情景记忆表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    strength REAL NOT NULL DEFAULT 0.7,
                    archived INTEGER NOT NULL DEFAULT 0,
                    event_timestamp INTEGER,
                    emotion TEXT,
                    importance REAL NOT NULL DEFAULT 0.5,
                    source TEXT NOT NULL DEFAULT 'user',
                    confidence REAL NOT NULL DEFAULT 1.0
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_episodic_char ON episodic_memories(character_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_episodic_text ON episodic_memories(text)")
            
            # 语义记忆表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    strength REAL NOT NULL DEFAULT 0.8,
                    archived INTEGER NOT NULL DEFAULT 0,
                    source_memory_ids TEXT,
                    confidence REAL NOT NULL DEFAULT 0.9,
                    category TEXT NOT NULL DEFAULT 'preference'
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_char ON semantic_memories(character_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memories(category)")
            
            # 记忆标签表（共享）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_tags (
                    memory_id INTEGER NOT NULL,
                    memory_type TEXT NOT NULL,
                    phrase TEXT NOT NULL,
                    weight REAL NOT NULL,
                    PRIMARY KEY (memory_id, memory_type, phrase)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_mid ON memory_tags(memory_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_phrase ON memory_tags(phrase)")
            
            self.conn.commit()
    
    def _init_embedding(self, model_name: str):
        """初始化嵌入模型"""
        try:
            print(f"[Memory] 加载嵌入模型：{model_name}")
            self.model = SentenceTransformer(model_name)
            self.dim = self.model.get_sentence_embedding_dimension()
            
            # 初始化 FAISS 索引
            self.index = faiss.IndexFlatIP(self.dim)  # 内积 = 余弦相似度（归一化后）
            
            print(f"[Memory] 嵌入模型已加载，维度：{self.dim}")
        except Exception as e:
            print(f"[Memory] 加载嵌入模型失败：{e}")
            self.model = None
    
    def _embed(self, texts: List[str]) -> np.ndarray:
        """计算文本嵌入"""
        if not self.model:
            raise RuntimeError("嵌入模型未初始化")
        
        vecs = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,  # L2 归一化
        )
        return np.asarray(vecs, dtype=np.float32)
    
    def _load_or_rebuild_index(self):
        """加载或重建 FAISS 索引"""
        if not os.path.exists(self.index_path) or not os.path.exists(self.ids_path):
            self._rebuild_index()
            return
        
        try:
            self.index = faiss.read_index(self.index_path)
            self.id_map = np.load(self.ids_path).astype(np.int64).tolist()
            
            if self.index.ntotal != len(self.id_map):
                raise ValueError("Index 和 id_map 大小不匹配")
            
            print(f"[Memory] FAISS 索引已加载：{self.index.ntotal} 条")
        except Exception as e:
            print(f"[Memory] 加载 FAISS 索引失败：{e}，重建中...")
            self._rebuild_index()
    
    def _rebuild_index(self):
        """重建 FAISS 索引"""
        if not self.model:
            return
        
        # 读取所有情景记忆
        rows = self._fetch_all_episodic()
        if not rows:
            self._persist_index()
            return
        
        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]
        
        # 计算嵌入
        vecs = self._embed(texts)
        
        # 重建索引
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vecs)
        self.id_map = ids
        
        self._persist_index()
        print(f"[Memory] FAISS 索引已重建：{len(ids)} 条")
    
    def _persist_index(self):
        """保存 FAISS 索引"""
        if self.index:
            faiss.write_index(self.index, self.index_path)
        np.save(self.ids_path, np.asarray(self.id_map, dtype=np.int64))
    
    def _fetch_all_episodic(self) -> List[Tuple[int, str]]:
        """获取所有情景记忆"""
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT id, text FROM episodic_memories WHERE character_id=? AND archived=0 ORDER BY id ASC",
            (self.character_id,)
        ).fetchall()
        return [(int(r[0]), str(r[1])) for r in rows]
    
    def _fetch_all_semantic(self) -> List[Tuple[int, str]]:
        """获取所有语义记忆"""
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT id, text FROM semantic_memories WHERE character_id=? AND archived=0 ORDER BY id ASC",
            (self.character_id,)
        ).fetchall()
        return [(int(r[0]), str(r[1])) for r in rows]
    
    def _load_tags_cache(self):
        """加载标签缓存"""
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT memory_id, phrase, weight FROM memory_tags"
        ).fetchall()
        
        cache: Dict[int, List[Tuple[str, float]]] = {}
        for mid, phrase, w in rows:
            cache.setdefault(int(mid), []).append((str(phrase), float(w)))
        
        # 按权重排序
        for mid in cache:
            cache[mid].sort(key=lambda x: x[1], reverse=True)
        
        self.tag_cache = cache
    
    # ========== 记忆写入 ==========
    
    def add(
        self,
        text: str,
        memory_type: str = "episodic",
        emotion: Optional[str] = None,
        importance: float = 0.5,
        source: str = "user",
        confidence: float = 1.0,
        category: str = "preference",
        source_memory_ids: Optional[List[int]] = None,
    ) -> Optional[int]:
        """
        添加记忆
        
        Args:
            text: 记忆内容
            memory_type: episodic/semantic
            emotion: 情绪标记
            importance: 重要性评分
            source: 来源（user/assistant/system/inference）
            confidence: 置信度
            category: 类别（仅语义记忆）
            source_memory_ids: 来源记忆 ID 列表（仅语义记忆）
        
        Returns:
            记忆 ID，失败返回 None
        """
        ts = int(time.time())
        
        if memory_type == "episodic":
            return self._add_episodic(
                text=text,
                emotion=emotion,
                importance=importance,
                source=source,
                confidence=confidence,
            )
        elif memory_type == "semantic":
            return self._add_semantic(
                text=text,
                category=category,
                source_memory_ids=source_memory_ids or [],
                confidence=confidence,
            )
        else:
            print(f"[Memory] 未知记忆类型：{memory_type}")
            return None
    
    def _add_episodic(
        self,
        text: str,
        emotion: Optional[str],
        importance: float,
        source: str,
        confidence: float,
    ) -> Optional[int]:
        """添加情景记忆"""
        ts = int(time.time())
        
        with self._db_lock:
            cur = self.conn.cursor()
            
            try:
                # 插入记忆
                cur.execute("""
                    INSERT INTO episodic_memories
                    (character_id, text, created_at, last_seen, emotion, importance, source, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.character_id, text, ts, ts, emotion, importance, source, confidence))
                
                memory_id = cur.lastrowid
                
                # 提取并保存标签
                tags = self._extract_tags(text)
                self._save_tags(memory_id, "episodic", tags)
                
                self.conn.commit()
                
                # 更新向量索引
                if self.model and tags:
                    self._add_to_index(memory_id, text)
                
                return memory_id
                
            except sqlite3.IntegrityError as e:
                # 重复记忆，更新 last_seen
                cur.execute("""
                    UPDATE episodic_memories
                    SET last_seen=?, seen_count=seen_count+1, strength=MIN(1.0, strength+0.01)
                    WHERE character_id=? AND text=?
                """, (ts, self.character_id, text))
                self.conn.commit()
                
                # 获取现有 ID
                row = cur.execute(
                    "SELECT id FROM episodic_memories WHERE character_id=? AND text=?",
                    (self.character_id, text)
                ).fetchone()
                return row[0] if row else None
    
    def _add_semantic(
        self,
        text: str,
        category: str,
        source_memory_ids: List[int],
        confidence: float,
    ) -> Optional[int]:
        """添加语义记忆"""
        ts = int(time.time())
        
        with self._db_lock:
            cur = self.conn.cursor()
            
            try:
                cur.execute("""
                    INSERT INTO semantic_memories
                    (character_id, text, created_at, last_seen, category, source_memory_ids, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (self.character_id, text, ts, ts, category, json.dumps(source_memory_ids), confidence))
                
                memory_id = cur.lastrowid
                
                # 提取并保存标签
                tags = self._extract_tags(text)
                self._save_tags(memory_id, "semantic", tags)
                
                self.conn.commit()
                
                # 更新向量索引
                if self.model and tags:
                    self._add_to_index(memory_id, text)
                
                return memory_id
                
            except Exception as e:
                print(f"[Memory] 添加语义记忆失败：{e}")
                return None
    
    def _add_to_index(self, memory_id: int, text: str):
        """添加到向量索引"""
        if not self.model or not self.index:
            return
        
        try:
            vec = self._embed([text])
            self.index.add(vec)
            self.id_map.append(memory_id)
            self._persist_index()
        except Exception as e:
            print(f"[Memory] 添加到索引失败：{e}")
    
    def _extract_tags(self, text: str, max_tags: int = 6) -> List[MemoryTag]:
        """
        从文本提取标签（带权重）
        
        使用轻量级短语抽取 + 嵌入打分
        """
        if not text.strip():
            return []
        
        # 抽取中文短语候选（n-gram）
        cands = self._phrase_candidates(text)
        if not cands:
            return []
        
        # 如果没有模型，返回简单标签
        if not self.model:
            return [MemoryTag(phrase=p, weight=1.0/len(cands)) for p in cands[:max_tags]]
        
        # 用嵌入打分
        try:
            sv = self._embed([text])[0]
            cv = self._embed(cands)
            sims = cv @ sv
            
            # 取 top
            n = min(max_tags, len(cands))
            top_idx = np.argsort(-sims)[:n]
            
            # Softmax 归一化
            top_sims = sims[top_idx] * 8.0
            weights = np.exp(top_sims) / np.sum(np.exp(top_sims))
            
            tags = [MemoryTag(phrase=cands[i], weight=float(weights[j])) for j, i in enumerate(top_idx)]
            tags.sort(key=lambda t: t.weight, reverse=True)
            
            return tags
        except Exception as e:
            print(f"[Memory] 提取标签失败：{e}")
            return [MemoryTag(phrase=p, weight=1.0/len(cands)) for p in cands[:max_tags]]
    
    def _phrase_candidates(self, text: str, max_candidates: int = 80) -> List[str]:
        """从中文文本抽取短语候选"""
        # 简单实现：中文字符 n-gram
        zh_pattern = re.compile(r'[\u4e00-\u9fff]+')
        chunks = zh_pattern.findall(text)
        if not chunks:
            return []
        
        s = "".join(chunks)
        cands = []
        
        # n-gram: 2~5 字
        for n in range(2, 6):
            for i in range(len(s) - n + 1):
                p = s[i:i+n]
                if p not in cands:
                    cands.append(p)
        
        return cands[:max_candidates]
    
    def _save_tags(self, memory_id: int, memory_type: str, tags: List[MemoryTag]):
        """保存标签"""
        if not tags:
            return
        
        with self._db_lock:
            cur = self.conn.cursor()
            for tag in tags:
                cur.execute("""
                    INSERT OR REPLACE INTO memory_tags (memory_id, memory_type, phrase, weight)
                    VALUES (?, ?, ?, ?)
                """, (memory_id, memory_type, tag.phrase, tag.weight))
            self.conn.commit()
        
        # 更新缓存
        self.tag_cache[memory_id] = [(t.phrase, t.weight) for t in tags]
    
    # ========== 记忆检索 ==========
    
    def retrieve(
        self,
        query: str,
        k: int = 6,
        memory_type: str = "episodic",
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        检索记忆
        
        Args:
            query: 查询文本
            k: 返回数量
            memory_type: episodic/semantic
            include_archived: 是否包含归档记忆
        
        Returns:
            记忆列表（带元数据）
        """
        if not query.strip():
            return []
        
        # 话题熔断检查
        if self.breaker_state.active:
            query = self._apply_breaker_filter(query)
        
        # 向量检索
        candidate_ids = self._retrieve_vector(query, k * 5)
        
        # 获取记忆详情
        memories = self._get_memories_by_ids(candidate_ids, memory_type, include_archived)
        
        # 综合评分 rerank
        scored = self._rerank(query, memories)
        
        # 取 top-k
        top_k = scored[:k]
        
        # 更新 last_seen
        self._update_last_seen([m["id"] for m in top_k], memory_type)
        
        return top_k
    
    def _retrieve_vector(self, query: str, k: int) -> List[int]:
        """向量检索"""
        if not self.model or not self.index or self.index.ntotal == 0:
            return []
        
        try:
            qv = self._embed([query])
            sims, idxs = self.index.search(qv, k)
            
            ids = []
            for i in idxs[0]:
                if 0 <= i < len(self.id_map):
                    ids.append(self.id_map[i])
            
            return ids
        except Exception as e:
            print(f"[Memory] 向量检索失败：{e}")
            return []
    
    def _get_memories_by_ids(
        self,
        ids: List[int],
        memory_type: str,
        include_archived: bool,
    ) -> List[Dict[str, Any]]:
        """根据 ID 获取记忆详情"""
        if not ids:
            return []
        
        with self._db_lock:
            cur = self.conn.cursor()
            
            if memory_type == "episodic":
                qmarks = ",".join(["?"] * len(ids))
                archived_filter = "" if include_archived else "AND archived=0"
                rows = cur.execute(f"""
                    SELECT id, text, created_at, last_seen, seen_count, strength,
                           emotion, importance, source, confidence
                    FROM episodic_memories
                    WHERE id IN ({qmarks}) {archived_filter}
                """, ids).fetchall()
                
                return [{
                    "id": r[0],
                    "text": r[1],
                    "created_at": r[2],
                    "last_seen": r[3],
                    "seen_count": r[4],
                    "strength": r[5],
                    "emotion": r[6],
                    "importance": r[7],
                    "source": r[8],
                    "confidence": r[9],
                    "type": "episodic",
                } for r in rows]
            
            elif memory_type == "semantic":
                qmarks = ",".join(["?"] * len(ids))
                archived_filter = "" if include_archived else "AND archived=0"
                rows = cur.execute(f"""
                    SELECT id, text, created_at, last_seen, seen_count, strength,
                           category, confidence
                    FROM semantic_memories
                    WHERE id IN ({qmarks}) {archived_filter}
                """, ids).fetchall()
                
                return [{
                    "id": r[0],
                    "text": r[1],
                    "created_at": r[2],
                    "last_seen": r[3],
                    "seen_count": r[4],
                    "strength": r[5],
                    "category": r[6],
                    "confidence": r[7],
                    "type": "semantic",
                } for r in rows]
        
        return []
    
    def _rerank(self, query: str, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """综合评分重排序"""
        now = int(time.time())
        scored = []
        
        for mem in memories:
            # 语义相似度（FAISS 已排序，这里简化处理）
            sim_score = 1.0 - (len(scored) * 0.05)  # 简化：按检索顺序递减
            
            # 时间新鲜度
            rec = recency_score(
                mem["last_seen"],
                now,
                half_life_days=7.0,
            )
            
            # 记忆权重（遗忘 + 强化）
            w = memory_weight(
                now,
                mem["last_seen"],
                mem["seen_count"],
                mem["strength"],
                half_life_days=self.config.half_life_days,
                alpha=self.config.alpha_reinforce,
            )
            
            # 标签匹配
            kw = 0.0
            tags = self.tag_cache.get(mem["id"], [])
            if tags:
                kw = sum(tw for phrase, tw in tags if phrase in query)
                kw = min(1.0, kw)
            
            # 综合分
            final = (
                self.config.semantic_weight * sim_score +
                self.config.recency_weight * rec +
                self.config.emotion_weight * (1.0 if mem.get("emotion") else 0.0) +
                self.config.task_weight * kw
            )
            
            mem["score"] = final
            scored.append(mem)
        
        # 按分数排序
        scored.sort(key=lambda m: m["score"], reverse=True)
        return scored
    
    def _update_last_seen(self, ids: List[int], memory_type: str):
        """更新 last_seen"""
        if not ids:
            return
        
        ts = int(time.time())
        
        with self._db_lock:
            cur = self.conn.cursor()
            
            if memory_type == "episodic":
                for mid in ids:
                    cur.execute("""
                        UPDATE episodic_memories
                        SET last_seen=?, seen_count=seen_count+1, strength=MIN(1.0, strength+0.01)
                        WHERE id=?
                    """, (ts, mid))
            elif memory_type == "semantic":
                for mid in ids:
                    cur.execute("""
                        UPDATE semantic_memories
                        SET last_seen=?, seen_count=seen_count+1, strength=MIN(1.0, strength+0.01)
                        WHERE id=?
                    """, (ts, mid))
            
            self.conn.commit()
    
    def _apply_breaker_filter(self, query: str) -> str:
        """应用话题熔断过滤"""
        # 简化实现：如果查询包含熔断标签，解除熔断
        if self.breaker_state.tag.lower() in query.lower():
            self.breaker_state.active = False
            self.breaker_state.tag = ""
            print(f"[Memory] 话题熔断已解除：{self.breaker_state.tag}")
        
        return query
    
    # ========== 记忆巩固 ==========
    
    def consolidate(self, batch_size: int = 10):
        """
        记忆巩固：从情景记忆提炼语义记忆
        
        定期调用（如每天一次）
        """
        print("[Memory] 开始记忆巩固...")
        
        # 获取最近的情景记忆
        with self._db_lock:
            cur = self.conn.cursor()
            rows = cur.execute("""
                SELECT id, text, emotion, importance
                FROM episodic_memories
                WHERE character_id=? AND archived=0
                ORDER BY created_at DESC
                LIMIT ?
            """, (self.character_id, batch_size)).fetchall()
        
        if not rows:
            return
        
        # 简单提炼：提取稳定偏好
        for row in rows:
            mem_id, text, emotion, importance = row
            
            # 高重要性记忆 → 语义记忆
            if importance > 0.7:
                # 简化提炼：直接复制（实际应用 LLM 提炼）
                semantic_text = f"用户偏好：{text}"
                
                self.add(
                    text=semantic_text,
                    memory_type="semantic",
                    category="preference",
                    source_memory_ids=[mem_id],
                    confidence=0.8,
                )
        
        print(f"[Memory] 记忆巩固完成：处理{len(rows)}条")
    
    # ========== 工具方法 ==========
    
    def count(self, memory_type: str = "episodic") -> int:
        """获取记忆数量"""
        with self._db_lock:
            cur = self.conn.cursor()
            
            if memory_type == "episodic":
                row = cur.execute(
                    "SELECT COUNT(*) FROM episodic_memories WHERE character_id=? AND archived=0",
                    (self.character_id,)
                ).fetchone()
            else:
                row = cur.execute(
                    "SELECT COUNT(*) FROM semantic_memories WHERE character_id=? AND archived=0",
                    (self.character_id,)
                ).fetchone()
            
            return row[0] if row else 0
    
    def clear(self):
        """清空所有记忆"""
        with self._db_lock:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM episodic_memories WHERE character_id=?", (self.character_id,))
            cur.execute("DELETE FROM semantic_memories WHERE character_id=?", (self.character_id,))
            cur.execute("DELETE FROM memory_tags WHERE memory_id IN (SELECT id FROM episodic_memories WHERE character_id=?)", (self.character_id,))
            self.conn.commit()
        
        # 重建索引
        if self.model:
            self._rebuild_index()
        
        print(f"[Memory] 记忆已清空：{self.character_id}")
    
    def export(self) -> Dict[str, Any]:
        """导出所有记忆"""
        with self._db_lock:
            cur = self.conn.cursor()
            
            episodic = cur.execute(
                "SELECT * FROM episodic_memories WHERE character_id=?",
                (self.character_id,)
            ).fetchall()
            
            semantic = cur.execute(
                "SELECT * FROM semantic_memories WHERE character_id=?",
                (self.character_id,)
            ).fetchall()
        
        return {
            "character_id": self.character_id,
            "episodic": episodic,
            "semantic": semantic,
            "config": self.config.to_dict() if hasattr(self.config, "to_dict") else {},
        }
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
