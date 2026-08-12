import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { prisma } from '../prisma';

export interface AuthUser {
  id: string;
  username: string;
  name: string;
  role: string;
  orgId: string | null;
  dataScope: string;
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
    }
  }
}

const JWT_SECRET = process.env.JWT_SECRET || 'recruit-agent-dev-secret';

export function signToken(user: AuthUser) {
  return jwt.sign(user, JWT_SECRET, { expiresIn: '7d' });
}

export async function authRequired(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) {
    return res.status(401).json({ message: '未登录或令牌无效' });
  }
  try {
    const payload = jwt.verify(header.slice(7), JWT_SECRET) as AuthUser;
    const user = await prisma.user.findUnique({ where: { id: payload.id } });
    if (!user || !user.active) {
      return res.status(401).json({ message: '账号不存在或已停用' });
    }
    req.user = {
      id: user.id,
      username: user.username,
      name: user.name,
      role: user.role,
      orgId: user.orgId,
      dataScope: user.dataScope,
    };
    next();
  } catch {
    return res.status(401).json({ message: '令牌已过期，请重新登录' });
  }
}

export function requireRoles(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) return res.status(401).json({ message: '未登录' });
    if (req.user.role === 'ADMIN' || roles.includes(req.user.role)) return next();
    return res.status(403).json({ message: '无权限执行此操作' });
  };
}

export const ROLE_LABELS: Record<string, string> = {
  ADMIN: '系统管理员',
  RECRUIT_LEAD: '招聘负责人',
  HR: '招聘HR',
  DEPT_HEAD: '用人部门负责人',
  INTERVIEWER: '面试官',
  OFFER_APPROVER: 'Offer审批人',
  HR_OPS: '人事运营',
  DATA_VIEWER: '数据查看人',
};
