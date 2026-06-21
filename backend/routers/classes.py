"""
班级管理路由 — 教师管理班级/邀请码/学生，学生通过邀请码加入
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Class, InviteCode, ClassStudent, Student, Teacher
from schemas import (
    ClassCreate, InviteCodeGenerate, JoinClass, AssignStudent,
    StudentInClass, InviteCodeInfo,
)
from utils.auth import require_teacher, require_student

router = APIRouter()


def generate_invite_code(length=8) -> str:
    """生成随机邀请码"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ===== 教师端 =====

@router.post("/")
async def create_class(
    body: ClassCreate,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师创建班级"""
    teacher = current_user[0]
    cls = Class(
        name=body.name,
        teacher_id=teacher.id,
        school_level=body.school_level,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return {
        "id": cls.id,
        "name": cls.name,
        "school_level": cls.school_level,
        "created_at": cls.created_at.isoformat(),
        "message": "班级创建成功",
    }


@router.get("/")
async def list_classes(
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师查看自己的班级列表"""
    teacher = current_user[0]
    classes = db.query(Class).filter(Class.teacher_id == teacher.id).order_by(Class.created_at.desc()).all()
    result = []
    for cls in classes:
        student_count = db.query(ClassStudent).filter(ClassStudent.class_id == cls.id).count()
        result.append({
            "id": cls.id,
            "name": cls.name,
            "school_level": cls.school_level,
            "student_count": student_count,
            "created_at": cls.created_at.isoformat(),
        })
    return result


@router.get("/{class_id}")
async def get_class_detail(
    class_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """获取班级详情（含成员列表）"""
    teacher = current_user[0]
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    members = (
        db.query(ClassStudent, Student)
        .join(Student, ClassStudent.student_id == Student.id)
        .filter(ClassStudent.class_id == class_id)
        .all()
    )
    students = []
    for cs, stu in members:
        students.append({
            "id": stu.id,
            "name": stu.name,
            "student_id": stu.student_id,
            "school_level": stu.school_level,
            "joined_via": cs.joined_via,
            "joined_at": cs.joined_at.isoformat() if cs.joined_at else None,
            "last_login": stu.last_login.isoformat() if stu.last_login else None,
        })

    return {
        "id": cls.id,
        "name": cls.name,
        "school_level": cls.school_level,
        "student_count": len(students),
        "students": students,
        "created_at": cls.created_at.isoformat(),
    }


@router.delete("/{class_id}")
async def delete_class(
    class_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师删除班级"""
    teacher = current_user[0]
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    db.delete(cls)
    db.commit()
    return {"message": "班级已删除"}


@router.post("/{class_id}/invite-codes")
async def generate_invite_code(
    class_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
    max_used_count: int = 0,
    expires_in_days: Optional[int] = None,
):
    """为班级生成邀请码（max_used_count=0 不限次数，expires_in_days 为空不过期）"""
    teacher = current_user[0]
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 生成唯一邀请码
    while True:
        code = generate_invite_code()
        existing = db.query(InviteCode).filter(InviteCode.code == code).first()
        if not existing:
            break

    invite = InviteCode(
        class_id=class_id,
        code=code,
        max_used_count=max_used_count,
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            if expires_in_days else None
        ),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "code": invite.code,
        "max_used_count": invite.max_used_count,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "created_at": invite.created_at.isoformat(),
    }


@router.get("/{class_id}/invite-codes")
async def list_invite_codes(
    class_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """查看班级的邀请码列表"""
    teacher = current_user[0]
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    codes = db.query(InviteCode).filter(InviteCode.class_id == class_id).order_by(InviteCode.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "max_used_count": c.max_used_count,
            "used_count": c.used_count,
            "is_active": c.is_active,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "created_at": c.created_at.isoformat(),
        }
        for c in codes
    ]


@router.delete("/invite-codes/{code_id}")
async def deactivate_invite_code(
    code_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """停用邀请码"""
    code = db.query(InviteCode).get(code_id)
    if not code:
        raise HTTPException(status_code=404, detail="邀请码不存在")

    # 验证该邀请码属于当前教师的班级
    cls = db.query(Class).filter(Class.id == code.class_id, Class.teacher_id == current_user[0].id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="无权操作此邀请码")

    code.is_active = False
    db.commit()
    return {"message": "邀请码已停用"}


@router.post("/{class_id}/students")
async def add_student_manual(
    class_id: int,
    body: AssignStudent,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师手动添加学生到班级"""
    teacher = current_user[0]
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    student = db.query(Student).get(body.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 检查是否已在某个班级
    existing = db.query(ClassStudent).filter(ClassStudent.student_id == body.student_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该学生已在班级中")

    cs = ClassStudent(
        student_id=body.student_id,
        class_id=class_id,
        joined_via="manual",
    )
    db.add(cs)
    db.commit()
    return {"message": f"已将 {student.name} 添加到班级 {cls.name}"}


@router.delete("/{class_id}/students/{student_id}")
async def remove_student(
    class_id: int,
    student_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """从班级移除学生"""
    teacher = current_user[0]
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    cs = db.query(ClassStudent).filter(
        ClassStudent.class_id == class_id,
        ClassStudent.student_id == student_id,
    ).first()
    if not cs:
        raise HTTPException(status_code=404, detail="学生不在该班级中")

    db.delete(cs)
    db.commit()
    return {"message": "已从班级移除"}


# ===== 学生端 =====

@router.post("/join")
async def join_class(
    body: JoinClass,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """学生通过邀请码加入班级"""
    student = current_user[0]

    # 检查是否已在班级
    existing = db.query(ClassStudent).filter(ClassStudent.student_id == student.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="你已经在班级中，无法重复加入")

    # 查找邀请码
    invite = db.query(InviteCode).filter(InviteCode.code == body.code, InviteCode.is_active == True).first()
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码无效或已停用")

    # 检查过期
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        invite.is_active = False
        db.commit()
        raise HTTPException(status_code=400, detail="邀请码已过期")

    # 检查使用次数
    if invite.max_used_count > 0 and invite.used_count >= invite.max_used_count:
        invite.is_active = False
        db.commit()
        raise HTTPException(status_code=400, detail="邀请码已达使用上限")

    # 加入班级
    cs = ClassStudent(
        student_id=student.id,
        class_id=invite.class_id,
        joined_via="invite",
    )
    db.add(cs)
    invite.used_count += 1
    db.commit()

    cls = db.query(Class).get(invite.class_id)
    return {
        "message": f"成功加入班级 {cls.name}",
        "class_id": cls.id,
        "class_name": cls.name,
    }


@router.get("/my")
async def my_class(
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """查看自己所在的班级"""
    student = current_user[0]
    cs = db.query(ClassStudent).filter(ClassStudent.student_id == student.id).first()
    if not cs:
        return None

    cls = db.query(Class).get(cs.class_id)
    teacher = db.query(Teacher).get(cls.teacher_id) if cls else None

    return {
        "class_id": cls.id,
        "class_name": cls.name,
        "school_level": cls.school_level,
        "teacher_name": teacher.name if teacher else "未知",
        "joined_via": cs.joined_via,
        "joined_at": cs.joined_at.isoformat() if cs.joined_at else None,
    }
