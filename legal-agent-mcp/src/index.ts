#!/usr/bin/env node
/**
 * Legal Agent MCP Server — exposes legal search, chat, and contract tools via stdio.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'

import { LegalAgentClient } from './legal-client.js'
import { handleToolCall, TOOL_DEFINITIONS } from './tools.js'

async function main(): Promise<void> {
  const client = LegalAgentClient.fromEnv()

  const server = new Server(
    { name: 'legal-agent-mcp', version: '0.1.0' },
    { capabilities: { tools: {} } },
  )

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS.map(({ name, description, inputSchema }) => ({
      name,
      description,
      inputSchema,
    })),
  }))

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params
    const result = await handleToolCall(client, name, args ?? {})
    return result
  })

  const transport = new StdioServerTransport()
  await server.connect(transport)
}

main().catch((err) => {
  console.error('legal-agent-mcp fatal:', err)
  process.exit(1)
})
