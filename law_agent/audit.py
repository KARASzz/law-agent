"""
审计日志模块 (Audit Logging)

职责：
1. 记录所有任务执行的审计日志
2. 支持日志查询和导出
3. 支持合规审计

审计内容：
- task_id: 任务ID
- session_id: 会话ID
- trace_id: 链路ID
- user_id: 用户ID
- intent: 意图类型
- input_summary: 输入摘要
- output_summary: 输出摘要
- tools_used: 使用的工具
- risk_level: 风险等级
- confirmed: 是否确认
- exported: 是否导出
- timestamp: 时间戳
"""

from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
from enum import Enum
import json
import sqlite3
from pathlib import Path

from law_agent.storage_sqlmodel import (
    SQLMODEL_AVAILABLE,
    AuditLogRecord,
    ExportLogRecord,
    ExternalActionLogRecord,
    create_sqlite_engine,
    create_storage_tables,
)

if SQLMODEL_AVAILABLE:  # pragma: no cover - covered by adapter tests when installed
    from sqlmodel import Session, select


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLog:
    """审计日志条目"""
    task_id: str
    session_id: str
    trace_id: str
    user_id: str
    intent: str
    input_summary: str
    output_summary: str
    tools_used: str  # 逗号分隔的工具列表
    risk_level: str
    confirmed: bool = False
    exported: bool = False
    log_level: str = LogLevel.INFO.value
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        """转换为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """
    审计日志记录器
    
    使用SQLite存储审计日志
    支持查询、导出和合规审计
    """
    
    def __init__(self, db_path: str = "data/audit.db", use_sqlmodel: bool = False):
        self.db_path = db_path
        self._memory_conn = None
        self._use_sqlmodel = use_sqlmodel and SQLMODEL_AVAILABLE
        self._engine = None
        if self._use_sqlmodel:
            self._engine = create_sqlite_engine(db_path)
            create_storage_tables(
                self._engine,
                [AuditLogRecord, ExportLogRecord, ExternalActionLogRecord],
            )
        else:
            self._init_database()

    def _connect(self):
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(self.db_path)
            return self._memory_conn
        return sqlite3.connect(self.db_path)

    def _close(self, conn):
        if self.db_path != ":memory:":
            conn.close()

    def _audit_record_to_log(self, record) -> AuditLog:
        return AuditLog(
            task_id=record.task_id,
            session_id=record.session_id or "",
            trace_id=record.trace_id,
            user_id=record.user_id or "",
            intent=record.intent,
            input_summary=record.input_summary or "",
            output_summary=record.output_summary or "",
            tools_used=record.tools_used or "",
            risk_level=record.risk_level or "",
            confirmed=bool(record.confirmed),
            exported=bool(record.exported),
            log_level=record.log_level or LogLevel.INFO.value,
            error_message=record.error_message,
            timestamp=record.timestamp,
        )

    def _audit_time_value(self, value):
        if not value:
            return value
        return value.isoformat() if hasattr(value, "isoformat") else value

    def _get_audit_record(self, session, trace_id: str):
        return session.exec(
            select(AuditLogRecord).where(AuditLogRecord.trace_id == trace_id)
        ).first()
    
    def _init_database(self):
        """初始化数据库"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                session_id TEXT,
                trace_id TEXT NOT NULL,
                user_id TEXT,
                intent TEXT NOT NULL,
                input_summary TEXT,
                output_summary TEXT,
                tools_used TEXT,
                risk_level TEXT,
                confirmed INTEGER DEFAULT 0,
                exported INTEGER DEFAULT 0,
                log_level TEXT DEFAULT 'info',
                error_message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(trace_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON audit_logs(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON audit_logs(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_intent ON audit_logs(intent)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_level ON audit_logs(risk_level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)")
        
        # 导出记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                export_type TEXT,
                export_format TEXT,
                confirmed INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(trace_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                user_id TEXT,
                actor_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                export_format TEXT,
                destination TEXT,
                risk_level TEXT,
                review_status TEXT,
                confirmed INTEGER DEFAULT 0,
                reviewer_id TEXT,
                reviewed_at TEXT,
                original_output TEXT,
                final_output TEXT,
                profile_record_ids TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_external_action_trace_id ON external_action_logs(trace_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_external_action_user_id ON external_action_logs(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_external_action_type ON external_action_logs(action_type)"
        )
        
        conn.commit()
        self._close(conn)
    
    async def log(self, audit_log: AuditLog):
        """
        记录审计日志
        
        Args:
            audit_log: 审计日志条目
        """
        if self._use_sqlmodel:
            timestamp = self._audit_time_value(audit_log.timestamp)
            with Session(self._engine) as session:
                record = self._get_audit_record(session, audit_log.trace_id)
                if record:
                    record.confirmed = 1 if audit_log.confirmed else 0
                    record.exported = 1 if audit_log.exported else 0
                else:
                    record = AuditLogRecord(
                        task_id=audit_log.task_id,
                        session_id=audit_log.session_id,
                        trace_id=audit_log.trace_id,
                        user_id=audit_log.user_id,
                        intent=audit_log.intent,
                        input_summary=audit_log.input_summary,
                        output_summary=audit_log.output_summary,
                        tools_used=audit_log.tools_used,
                        risk_level=audit_log.risk_level,
                        confirmed=1 if audit_log.confirmed else 0,
                        exported=1 if audit_log.exported else 0,
                        log_level=audit_log.log_level,
                        error_message=audit_log.error_message,
                        timestamp=timestamp,
                    )
                    session.add(record)
                session.commit()
            return

        conn = self._connect()
        cursor = conn.cursor()
        timestamp = (
            audit_log.timestamp.isoformat()
            if hasattr(audit_log.timestamp, "isoformat")
            else audit_log.timestamp
        )
        
        try:
            cursor.execute("""
                INSERT INTO audit_logs (
                    task_id, session_id, trace_id, user_id, intent,
                    input_summary, output_summary, tools_used, risk_level,
                    confirmed, exported, log_level, error_message, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_log.task_id,
                audit_log.session_id,
                audit_log.trace_id,
                audit_log.user_id,
                audit_log.intent,
                audit_log.input_summary,
                audit_log.output_summary,
                audit_log.tools_used,
                audit_log.risk_level,
                1 if audit_log.confirmed else 0,
                1 if audit_log.exported else 0,
                audit_log.log_level,
                audit_log.error_message,
                timestamp,
            ))
            
            conn.commit()
            
        except sqlite3.IntegrityError:
            # 日志已存在，更新
            cursor.execute("""
                UPDATE audit_logs SET
                    confirmed = ?,
                    exported = ?
                WHERE trace_id = ?
            """, (
                1 if audit_log.confirmed else 0,
                1 if audit_log.exported else 0,
                audit_log.trace_id,
            ))
            conn.commit()
            
        finally:
            self._close(conn)
    
    async def log_export(
        self,
        task_id: str,
        trace_id: str,
        user_id: str,
        export_type: str = "document",
        export_format: str = "markdown",
        confirmed: bool = True,
    ):
        """
        记录导出日志
        
        Args:
            task_id: 任务ID
            trace_id: 链路ID
            user_id: 用户ID
            export_type: 导出类型
            export_format: 导出格式
            confirmed: 是否已确认
        """
        if self._use_sqlmodel:
            with Session(self._engine) as session:
                record = ExportLogRecord(
                    task_id=task_id,
                    trace_id=trace_id,
                    user_id=user_id,
                    export_type=export_type,
                    export_format=export_format,
                    confirmed=1 if confirmed else 0,
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                )
                session.add(record)
                audit_record = self._get_audit_record(session, trace_id)
                if audit_record:
                    audit_record.exported = 1
                session.commit()
            return

        conn = self._connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO export_logs (
                    task_id, trace_id, user_id, export_type,
                    export_format, confirmed, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, trace_id, user_id, export_type,
                export_format,
                1 if confirmed else 0,
                datetime.now().isoformat(timespec="seconds"),
            ))
            
            # 同时更新审计日志的导出标记
            cursor.execute("""
                UPDATE audit_logs SET exported = 1 WHERE trace_id = ?
            """, (trace_id,))
            
            conn.commit()
            
        finally:
            self._close(conn)

    async def log_external_action(
        self,
        task_id: str,
        trace_id: str,
        user_id: str,
        actor_id: str,
        action_type: str,
        export_format: str = "markdown",
        destination: str = "",
        risk_level: str = "",
        review_status: str = "not_required",
        confirmed: bool = False,
        reviewer_id: Optional[str] = None,
        reviewed_at: Optional[str] = None,
        original_output: str = "",
        final_output: str = "",
        profile_record_ids: Optional[List[str]] = None,
    ) -> dict:
        """记录导出或对外发送动作，并把主审计日志标记为已发生对外动作。"""
        profile_ids = profile_record_ids or []
        timestamp = datetime.now().isoformat(timespec="seconds")
        if self._use_sqlmodel:
            with Session(self._engine) as session:
                record = ExternalActionLogRecord(
                    task_id=task_id,
                    trace_id=trace_id,
                    user_id=user_id,
                    actor_id=actor_id,
                    action_type=action_type,
                    export_format=export_format,
                    destination=destination,
                    risk_level=risk_level,
                    review_status=review_status,
                    confirmed=1 if confirmed else 0,
                    reviewer_id=reviewer_id,
                    reviewed_at=reviewed_at,
                    original_output=original_output,
                    final_output=final_output,
                    profile_record_ids=",".join(profile_ids),
                    timestamp=timestamp,
                )
                session.add(record)
                audit_record = self._get_audit_record(session, trace_id)
                if audit_record:
                    audit_record.exported = 1
                session.commit()
                session.refresh(record)
                action_id = record.id
            return {
                "id": action_id,
                "task_id": task_id,
                "trace_id": trace_id,
                "user_id": user_id,
                "actor_id": actor_id,
                "action_type": action_type,
                "export_format": export_format,
                "destination": destination,
                "risk_level": risk_level,
                "review_status": review_status,
                "confirmed": confirmed,
                "reviewer_id": reviewer_id,
                "reviewed_at": reviewed_at,
                "original_output": original_output,
                "final_output": final_output,
                "profile_record_ids": profile_ids,
                "timestamp": timestamp,
            }

        conn = self._connect()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO external_action_logs (
                    task_id, trace_id, user_id, actor_id, action_type,
                    export_format, destination, risk_level, review_status,
                    confirmed, reviewer_id, reviewed_at, original_output,
                    final_output, profile_record_ids, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                trace_id,
                user_id,
                actor_id,
                action_type,
                export_format,
                destination,
                risk_level,
                review_status,
                1 if confirmed else 0,
                reviewer_id,
                reviewed_at,
                original_output,
                final_output,
                ",".join(profile_ids),
                timestamp,
            ))
            action_id = cursor.lastrowid

            cursor.execute("""
                UPDATE audit_logs SET exported = 1 WHERE trace_id = ?
            """, (trace_id,))

            conn.commit()

        finally:
            self._close(conn)

        return {
            "id": action_id,
            "task_id": task_id,
            "trace_id": trace_id,
            "user_id": user_id,
            "actor_id": actor_id,
            "action_type": action_type,
            "export_format": export_format,
            "destination": destination,
            "risk_level": risk_level,
            "review_status": review_status,
            "confirmed": confirmed,
            "reviewer_id": reviewer_id,
            "reviewed_at": reviewed_at,
            "original_output": original_output,
            "final_output": final_output,
            "profile_record_ids": profile_ids,
            "timestamp": timestamp,
        }

    async def set_confirmation(self, trace_id: str, confirmed: bool):
        """更新审计日志中的人工确认标记。"""
        if self._use_sqlmodel:
            with Session(self._engine) as session:
                record = self._get_audit_record(session, trace_id)
                if record:
                    record.confirmed = 1 if confirmed else 0
                    session.commit()
            return

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE audit_logs SET confirmed = ? WHERE trace_id = ?",
                (1 if confirmed else 0, trace_id),
            )
            conn.commit()
        finally:
            self._close(conn)

    async def get_by_trace_id(self, trace_id: str) -> Optional[AuditLog]:
        """按 trace_id 查询单条主审计日志。"""
        if self._use_sqlmodel:
            with Session(self._engine) as session:
                record = self._get_audit_record(session, trace_id)
                return self._audit_record_to_log(record) if record else None

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM audit_logs WHERE trace_id = ?",
                (trace_id,),
            )
            row = cursor.fetchone()
        finally:
            self._close(conn)

        if not row:
            return None

        data = self._audit_row_to_dict(row)
        return AuditLog(**data)

    async def query_external_actions(
        self,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """查询导出和对外发送审计明细。"""
        if self._use_sqlmodel:
            statement = select(ExternalActionLogRecord)
            if trace_id:
                statement = statement.where(ExternalActionLogRecord.trace_id == trace_id)
            if user_id:
                statement = statement.where(ExternalActionLogRecord.user_id == user_id)
            if action_type:
                statement = statement.where(ExternalActionLogRecord.action_type == action_type)
            statement = statement.order_by(ExternalActionLogRecord.timestamp.desc()).limit(limit)

            with Session(self._engine) as session:
                records = session.exec(statement).all()

            actions = []
            for record in records:
                actions.append(
                    {
                        "id": record.id,
                        "task_id": record.task_id,
                        "trace_id": record.trace_id,
                        "user_id": record.user_id,
                        "actor_id": record.actor_id,
                        "action_type": record.action_type,
                        "export_format": record.export_format,
                        "destination": record.destination,
                        "risk_level": record.risk_level,
                        "review_status": record.review_status,
                        "confirmed": bool(record.confirmed),
                        "reviewer_id": record.reviewer_id,
                        "reviewed_at": record.reviewed_at,
                        "original_output": record.original_output,
                        "final_output": record.final_output,
                        "profile_record_ids": (
                            record.profile_record_ids.split(",")
                            if record.profile_record_ids
                            else []
                        ),
                        "timestamp": record.timestamp,
                    }
                )
            return actions

        conn = self._connect()
        cursor = conn.cursor()

        conditions = []
        params = []

        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if action_type:
            conditions.append("action_type = ?")
            params.append(action_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM external_action_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        finally:
            self._close(conn)

        columns = [
            "id", "task_id", "trace_id", "user_id", "actor_id", "action_type",
            "export_format", "destination", "risk_level", "review_status",
            "confirmed", "reviewer_id", "reviewed_at", "original_output",
            "final_output", "profile_record_ids", "timestamp"
        ]
        actions = []
        for row in rows:
            data = dict(zip(columns, row))
            data["confirmed"] = bool(data["confirmed"])
            data["profile_record_ids"] = (
                data["profile_record_ids"].split(",")
                if data.get("profile_record_ids")
                else []
            )
            timestamp = data.get("timestamp")
            data["timestamp"] = (
                timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp
            )
            actions.append(data)

        return actions
    
    async def query(
        self,
        user_id: Optional[str] = None,
        intent: Optional[str] = None,
        risk_level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        查询审计日志
        
        Args:
            user_id: 用户ID
            intent: 意图类型
            risk_level: 风险等级
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            
        Returns:
            List[AuditLog]: 审计日志列表
        """
        if self._use_sqlmodel:
            statement = select(AuditLogRecord)
            if user_id:
                statement = statement.where(AuditLogRecord.user_id == user_id)
            if intent:
                statement = statement.where(AuditLogRecord.intent == intent)
            if risk_level:
                statement = statement.where(AuditLogRecord.risk_level == risk_level)
            if start_time:
                statement = statement.where(
                    AuditLogRecord.timestamp >= self._audit_time_value(start_time)
                )
            if end_time:
                statement = statement.where(
                    AuditLogRecord.timestamp <= self._audit_time_value(end_time)
                )
            statement = statement.order_by(AuditLogRecord.timestamp.desc()).limit(limit)
            with Session(self._engine) as session:
                records = session.exec(statement).all()
            return [self._audit_record_to_log(record) for record in records]

        conn = self._connect()
        cursor = conn.cursor()
        
        # 构建查询条件
        conditions = []
        params = []
        
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        
        if intent:
            conditions.append("intent = ?")
            params.append(intent)
        
        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        # 构建SQL
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM audit_logs 
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        self._close(conn)
        
        logs = []
        for row in rows:
            logs.append(AuditLog(**self._audit_row_to_dict(row)))
        
        return logs

    def _audit_row_to_dict(self, row) -> dict:
        """把 audit_logs 查询结果转换为 AuditLog 构造参数。"""
        columns = [
            "id", "task_id", "session_id", "trace_id", "user_id", "intent",
            "input_summary", "output_summary", "tools_used", "risk_level",
            "confirmed", "exported", "log_level", "error_message", "timestamp"
        ]
        data = dict(zip(columns, row))
        data.pop("id", None)
        data["confirmed"] = bool(data["confirmed"])
        data["exported"] = bool(data["exported"])
        return data
    
    async def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计数据
        """
        if self._use_sqlmodel:
            statement = select(AuditLogRecord)
            if start_time:
                statement = statement.where(
                    AuditLogRecord.timestamp >= self._audit_time_value(start_time)
                )
            if end_time:
                statement = statement.where(
                    AuditLogRecord.timestamp <= self._audit_time_value(end_time)
                )

            with Session(self._engine) as session:
                records = session.exec(statement).all()

            total_tasks = len(records)
            intent_stats = {}
            risk_stats = {}
            exported = 0
            confirmed = 0
            for record in records:
                intent_stats[record.intent] = intent_stats.get(record.intent, 0) + 1
                risk_stats[record.risk_level] = risk_stats.get(record.risk_level, 0) + 1
                exported += 1 if record.exported else 0
                confirmed += 1 if record.confirmed else 0

            return {
                "total_tasks": total_tasks,
                "intent_stats": intent_stats,
                "risk_stats": risk_stats,
                "export_rate": exported / total_tasks if total_tasks else 0,
                "confirm_rate": confirmed / total_tasks if total_tasks else 0,
            }

        conn = self._connect()
        cursor = conn.cursor()
        
        # 时间条件
        time_condition = ""
        params = []
        if start_time:
            time_condition += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            time_condition += " AND timestamp <= ?"
            params.append(end_time)
        
        # 总任务数
        cursor.execute(f"""
            SELECT COUNT(*) FROM audit_logs WHERE 1=1 {time_condition}
        """, params)
        total_tasks = cursor.fetchone()[0]
        
        # 按意图统计
        cursor.execute(f"""
            SELECT intent, COUNT(*) as count 
            FROM audit_logs 
            WHERE 1=1 {time_condition}
            GROUP BY intent
        """, params)
        intent_stats = dict(cursor.fetchall())
        
        # 按风险等级统计
        cursor.execute(f"""
            SELECT risk_level, COUNT(*) as count 
            FROM audit_logs 
            WHERE 1=1 {time_condition}
            GROUP BY risk_level
        """, params)
        risk_stats = dict(cursor.fetchall())
        
        # 导出率
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(exported) as exported
            FROM audit_logs 
            WHERE 1=1 {time_condition}
        """, params)
        export_row = cursor.fetchone()
        export_rate = export_row[1] / export_row[0] if export_row[0] > 0 else 0
        
        # 确认率
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(confirmed) as confirmed
            FROM audit_logs 
            WHERE 1=1 {time_condition}
        """, params)
        confirm_row = cursor.fetchone()
        confirm_rate = confirm_row[1] / confirm_row[0] if confirm_row[0] > 0 else 0
        
        self._close(conn)
        
        return {
            "total_tasks": total_tasks,
            "intent_stats": intent_stats,
            "risk_stats": risk_stats,
            "export_rate": export_rate,
            "confirm_rate": confirm_rate,
        }
    
    async def export_csv(self, filepath: str, **query_kwargs):
        """
        导出审计日志为CSV
        
        Args:
            filepath: 导出文件路径
            **query_kwargs: 查询参数
        """
        logs = await self.query(**query_kwargs)
        
        import csv
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            if logs:
                fieldnames = list(logs[0].to_dict().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for log in logs:
                    writer.writerow(log.to_dict())


# ===== 快捷函数 =====

def create_audit_logger(db_path: str = "data/audit.db") -> AuditLogger:
    """创建审计日志记录器"""
    return AuditLogger(db_path)
