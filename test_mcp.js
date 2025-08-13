#!/usr/bin/env node
/**
 * Test MCP server communication using Node.js
 */

const { spawn } = require('child_process');
const readline = require('readline');

async function testMCPServer() {
    console.log('Testing MCP Server Communication');
    console.log('='.repeat(60));
    
    // Start the MCP server
    const server = spawn('npx', ['@modelcontextprotocol/server-filesystem', '/tmp']);
    
    // Create readline interface for the server's stdout
    const rl = readline.createInterface({
        input: server.stdout,
        output: process.stdout,
        terminal: false
    });
    
    // Handle server messages
    rl.on('line', (line) => {
        console.log('📥 Server:', line);
        try {
            const message = JSON.parse(line);
            console.log('✅ Parsed:', JSON.stringify(message, null, 2));
        } catch (e) {
            // Not JSON, just a plain message
        }
    });
    
    // Handle server errors
    server.stderr.on('data', (data) => {
        console.log('⚠️ Server stderr:', data.toString());
    });
    
    // Send initialization request
    const initRequest = {
        jsonrpc: "2.0",
        method: "initialize",
        params: {
            protocolVersion: "1.0",
            capabilities: {
                roots: {},
                sampling: {}
            },
            clientInfo: {
                name: "test-client",
                version: "1.0.0"
            }
        },
        id: 1
    };
    
    console.log('\n📤 Sending initialization request...');
    server.stdin.write(JSON.stringify(initRequest) + '\n');
    
    // Wait a bit for response
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Send a tool request
    const toolRequest = {
        jsonrpc: "2.0",
        method: "tools/list",
        id: 2
    };
    
    console.log('\n📤 Sending tools/list request...');
    server.stdin.write(JSON.stringify(toolRequest) + '\n');
    
    // Wait for responses
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Clean up
    server.kill();
    console.log('\n✅ Test complete');
}

testMCPServer().catch(console.error);