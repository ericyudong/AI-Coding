import { Request } from 'express';
import { prisma } from '../prisma';

export async function writeAudit(
  req: Request,
  action: string,
  objectType: string,
  objectId?: string,
  oldValue?: unknown,
  newValue?: unknown,
  reason?: string
) {
  await prisma.auditLog.create({
    data: {
      userId: req.user?.id,
      userName: req.user?.name,
      action,
      objectType,
      objectId,
      oldValue: oldValue != null ? JSON.stringify(oldValue) : null,
      newValue: newValue != null ? JSON.stringify(newValue) : null,
      reason,
      ip: req.ip,
    },
  });
}

export async function writeActivity(data: {
  type: string;
  title: string;
  detail?: string;
  jobId?: string;
  relatedId?: string;
  actorId?: string;
  actorName?: string;
}) {
  await prisma.activity.create({ data });
}

export async function createTodo(data: {
  userId: string;
  type: string;
  title: string;
  refType?: string;
  refId?: string;
  dueAt?: Date;
}) {
  return prisma.todo.create({ data });
}

export async function completeTodos(refType: string, refId: string, type?: string) {
  await prisma.todo.updateMany({
    where: {
      refType,
      refId,
      done: false,
      ...(type ? { type } : {}),
    },
    data: { done: true, doneAt: new Date() },
  });
}

export async function addProcessEvent(data: {
  applicationId: string;
  type: string;
  fromStatus?: string;
  toStatus?: string;
  fromStage?: string;
  toStage?: string;
  operatorId?: string;
  operatorName?: string;
  reason?: string;
  detail?: string;
}) {
  return prisma.processEvent.create({ data });
}

export async function emitBusinessEvent(eventType: string, objectType: string, objectId: string, payload?: unknown) {
  return prisma.businessEvent.create({
    data: {
      eventType,
      objectType,
      objectId,
      payload: payload != null ? JSON.stringify(payload) : null,
    },
  });
}

export function maskSensitive<T extends Record<string, any>>(obj: T, fields: string[] = ['phone', 'email', 'baseSalary', 'performance', 'bonus', 'probationSalary']): T {
  const clone = { ...obj };
  for (const f of fields) {
    if (f in clone && clone[f] != null) clone[f] = '***';
  }
  return clone;
}
