const { PrismaClient } = require('@prisma/client');
const p = new PrismaClient();
(async () => {
  const c = await p.channel.findUnique({ where: { code: 'LIEPIN' } });
  if (!c) {
    await p.channel.create({
      data: {
        name: '猎聘',
        code: 'LIEPIN',
        type: 'SITE',
        accounts: { create: [{ accountName: '猎聘企业账号', externalId: 'liepin-demo-001' }] },
      },
    });
    console.log('created LIEPIN');
  } else {
    console.log('LIEPIN exists');
  }
  await p.$disconnect();
})().catch(async (e) => {
  console.error(e);
  await p.$disconnect();
  process.exit(1);
});
