#!/usr/bin/env python3
"""检查任务状态"""
import sys
sys.path.insert(0, '/app')

from app.core.mysql_client import SessionLocal
from app.models.task_queue import TaskQueue
from sqlalchemy import desc

db = SessionLocal()
try:
    task = db.query(TaskQueue).filter(
        TaskQueue.task_type == 'generate_template'
    ).order_by(desc(TaskQueue.created_at)).first()
    
    if task:
        print('📊 任务监控信息：')
        print(f'  任务ID: {task.task_id}')
        print(f'  状态: {task.status}')
        print(f'  进度: {task.progress}%')
        print(f'  当前步骤: {task.current_step}')
        print(f'  已完成步骤: {task.completed_steps}/{task.total_steps}')
        print(f'  创建时间: {task.created_at}')
        print(f'  开始时间: {task.started_at or "未开始"}')
        print(f'  完成时间: {task.completed_at or "未完成"}')
        if task.error_message:
            print(f'  ❌ 错误信息: {task.error_message}')
        if task.result:
            print(f'  ✅ 结果: {task.result}')
    else:
        print('未找到模板生成任务')
finally:
    db.close()

