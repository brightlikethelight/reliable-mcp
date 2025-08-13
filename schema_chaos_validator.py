#!/usr/bin/env python3
"""
MCP Schema Validator
Tests for common schema validation issues that developers actually encounter.
Focuses on practical problems like missing fields, wrong types, and malformed responses.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from mcp_client import MCPClient
from config import SERVERS


class SchemaIssue(Enum):
    """Types of schema validation issues."""
    MISSING_REQUIRED = "missing_required_field"
    WRONG_TYPE = "wrong_data_type"
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_JSON = "malformed_json"
    INCONSISTENT_NAMING = "inconsistent_field_naming"
    MISSING_ERROR_HANDLING = "missing_error_handling"
    INVALID_FORMAT = "invalid_format"
    SCHEMA_MISMATCH = "schema_mismatch"


@dataclass
class ValidationResult:
    """A schema validation result."""
    issue_type: SchemaIssue
    tool_name: str
    description: str
    severity: str  # "error", "warning", "info"
    suggestion: str


class SchemaValidator:
    """Validate MCP servers for common schema issues."""
    
    def __init__(self):
        self.results = []
        self.tools_tested = 0
        self.issues_found = 0
        self.warnings_found = 0
    
    async def validate_schema(self, server_name: str) -> Dict:
        """Run practical schema validation."""
        
        print(f"\n{'=' * 70}")
        print(f"SCHEMA VALIDATION: {server_name}")
        print(f"Testing for common schema issues")
        print(f"{'=' * 70}")
        
        client = MCPClient(server_name)
        
        try:
            await client.start()
            
            # Validate server metadata
            await self._validate_server_info(client)
            
            # Get and validate tools
            tools = await client.list_tools()
            
            if not tools:
                print("⚠️ No tools available - server may not be properly configured")
                self.results.append(ValidationResult(
                    issue_type=SchemaIssue.EMPTY_RESPONSE,
                    tool_name="server",
                    description="No tools returned by server",
                    severity="warning",
                    suggestion="Check server implementation returns tools array"
                ))
                return self._generate_report(server_name)
            
            print(f"\nFound {len(tools)} tools to validate")
            
            # Validate each tool
            for tool in tools[:10]:  # Test up to 10 tools
                await self._validate_tool(client, tool)
            
            await client.stop()
            
        except Exception as e:
            print(f"Error during validation: {e}")
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MALFORMED_JSON,
                tool_name="server",
                description=f"Server error: {str(e)}",
                severity="error",
                suggestion="Check server starts correctly and returns valid JSON-RPC"
            ))
        
        return self._generate_report(server_name)
    
    async def _validate_server_info(self, client: MCPClient):
        """Validate server metadata and info."""
        
        print("\n📋 Validating server metadata...")
        
        # Check if server provides proper info
        if hasattr(client, 'server_info'):
            info = client.server_info
            
            if not info:
                self.results.append(ValidationResult(
                    issue_type=SchemaIssue.MISSING_REQUIRED,
                    tool_name="server",
                    description="Server info missing",
                    severity="warning",
                    suggestion="Implement server info in initialize response"
                ))
            else:
                # Check for required fields
                if 'name' not in info:
                    self.results.append(ValidationResult(
                        issue_type=SchemaIssue.MISSING_REQUIRED,
                        tool_name="server",
                        description="Server name missing",
                        severity="warning",
                        suggestion="Add 'name' field to server info"
                    ))
                
                if 'version' not in info:
                    self.results.append(ValidationResult(
                        issue_type=SchemaIssue.MISSING_REQUIRED,
                        tool_name="server",
                        description="Server version missing",
                        severity="info",
                        suggestion="Add 'version' field to server info"
                    ))
    
    async def _validate_tool(self, client: MCPClient, tool: Dict):
        """Validate a single tool's schema."""
        
        tool_name = tool.get('name', 'unknown')
        print(f"\n🔧 Validating tool: {tool_name}")
        
        self.tools_tested += 1
        
        # Check tool metadata
        if 'name' not in tool:
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_REQUIRED,
                tool_name="unknown",
                description="Tool missing 'name' field",
                severity="error",
                suggestion="Every tool must have a 'name' field"
            ))
            self.issues_found += 1
            return
        
        if 'description' not in tool:
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_REQUIRED,
                tool_name=tool_name,
                description="Tool missing description",
                severity="warning",
                suggestion="Add description to help users understand the tool"
            ))
            self.warnings_found += 1
        
        # Check input schema
        input_schema = tool.get('inputSchema', {})
        
        if not input_schema:
            print(f"  ⚠️ No input schema defined")
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_REQUIRED,
                tool_name=tool_name,
                description="No input schema defined",
                severity="warning",
                suggestion="Define inputSchema to validate inputs"
            ))
            self.warnings_found += 1
        else:
            # Validate schema structure
            await self._validate_schema_structure(tool_name, input_schema)
            
            # Test with valid input
            await self._test_valid_input(client, tool_name, input_schema)
            
            # Test with missing required fields
            await self._test_missing_required(client, tool_name, input_schema)
            
            # Test with wrong types
            await self._test_wrong_types(client, tool_name, input_schema)
    
    def _validate_schema_structure(self, tool_name: str, schema: Dict):
        """Validate the structure of a schema."""
        
        # Check for common schema issues
        if 'type' not in schema:
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_REQUIRED,
                tool_name=tool_name,
                description="Schema missing 'type' field",
                severity="warning",
                suggestion="Add 'type': 'object' to schema"
            ))
            self.warnings_found += 1
        
        if schema.get('type') == 'object' and 'properties' not in schema:
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_REQUIRED,
                tool_name=tool_name,
                description="Object schema missing 'properties'",
                severity="warning",
                suggestion="Define properties for object schema"
            ))
            self.warnings_found += 1
        
        # Check field naming consistency
        if 'properties' in schema:
            properties = schema['properties']
            has_camel = any('_' not in name for name in properties.keys())
            has_snake = any('_' in name for name in properties.keys())
            
            if has_camel and has_snake:
                self.results.append(ValidationResult(
                    issue_type=SchemaIssue.INCONSISTENT_NAMING,
                    tool_name=tool_name,
                    description="Inconsistent field naming (mix of camelCase and snake_case)",
                    severity="info",
                    suggestion="Use consistent naming convention"
                ))
                self.warnings_found += 1
    
    async def _test_valid_input(self, client: MCPClient, tool_name: str, schema: Dict):
        """Test with valid input based on schema."""
        
        # Generate valid input based on schema
        valid_input = self._generate_valid_input(schema)
        
        try:
            result = await client.call_tool(tool_name, valid_input)
            
            if result is None:
                self.results.append(ValidationResult(
                    issue_type=SchemaIssue.EMPTY_RESPONSE,
                    tool_name=tool_name,
                    description="Tool returned empty response for valid input",
                    severity="warning",
                    suggestion="Ensure tool returns appropriate response"
                ))
                self.warnings_found += 1
            else:
                print(f"  ✅ Valid input accepted")
                
        except Exception as e:
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_ERROR_HANDLING,
                tool_name=tool_name,
                description=f"Error with valid input: {str(e)[:100]}",
                severity="error",
                suggestion="Tool should handle valid input without errors"
            ))
            self.issues_found += 1
    
    async def _test_missing_required(self, client: MCPClient, tool_name: str, schema: Dict):
        """Test behavior when required fields are missing."""
        
        required_fields = schema.get('required', [])
        
        if not required_fields:
            return  # No required fields to test
        
        # Test with empty input
        try:
            result = await client.call_tool(tool_name, {})
            
            # If it succeeded with empty input when fields are required, that's an issue
            self.results.append(ValidationResult(
                issue_type=SchemaIssue.MISSING_REQUIRED,
                tool_name=tool_name,
                description=f"Tool accepted empty input despite required fields: {required_fields}",
                severity="error",
                suggestion="Validate required fields before processing"
            ))
            self.issues_found += 1
            
        except Exception as e:
            # This is expected - tool should reject missing required fields
            if "required" in str(e).lower() or "missing" in str(e).lower():
                print(f"  ✅ Required fields properly validated")
            else:
                # Error message could be clearer
                self.results.append(ValidationResult(
                    issue_type=SchemaIssue.MISSING_ERROR_HANDLING,
                    tool_name=tool_name,
                    description="Unclear error message for missing required fields",
                    severity="info",
                    suggestion="Provide clear error messages for validation failures"
                ))
                self.warnings_found += 1
    
    async def _test_wrong_types(self, client: MCPClient, tool_name: str, schema: Dict):
        """Test behavior with wrong data types."""
        
        if 'properties' not in schema:
            return
        
        properties = schema['properties']
        
        for prop_name, prop_schema in properties.items():
            expected_type = prop_schema.get('type', 'string')
            
            # Generate wrong type value
            wrong_value = self._get_wrong_type_value(expected_type)
            
            if wrong_value is not None:
                test_input = {prop_name: wrong_value}
                
                try:
                    result = await client.call_tool(tool_name, test_input)
                    
                    # If it accepted wrong type, that's an issue
                    self.results.append(ValidationResult(
                        issue_type=SchemaIssue.WRONG_TYPE,
                        tool_name=tool_name,
                        description=f"Field '{prop_name}' accepted {type(wrong_value).__name__} instead of {expected_type}",
                        severity="error",
                        suggestion="Validate data types before processing"
                    ))
                    self.issues_found += 1
                    
                except Exception as e:
                    # This is expected - should reject wrong types
                    if "type" in str(e).lower() or expected_type in str(e).lower():
                        print(f"  ✅ Type validation working for '{prop_name}'")
                    else:
                        # Could have better error message
                        pass
    
    def _generate_valid_input(self, schema: Dict) -> Dict:
        """Generate valid input based on schema."""
        
        if schema.get('type') != 'object':
            return {}
        
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        valid_input = {}
        
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get('type', 'string')
            
            # Generate appropriate default value
            if prop_type == 'string':
                valid_input[prop_name] = 'test'
            elif prop_type == 'number':
                valid_input[prop_name] = 42
            elif prop_type == 'boolean':
                valid_input[prop_name] = True
            elif prop_type == 'array':
                valid_input[prop_name] = []
            elif prop_type == 'object':
                valid_input[prop_name] = {}
            
            # Only include required fields
            if prop_name not in required and len(valid_input) > len(required):
                break
        
        return valid_input
    
    def _get_wrong_type_value(self, expected_type: str):
        """Get a value of the wrong type for testing."""
        
        wrong_types = {
            'string': 123,
            'number': 'not_a_number',
            'boolean': 'true',  # String instead of boolean
            'array': 'not_an_array',
            'object': 'not_an_object'
        }
        
        return wrong_types.get(expected_type)
    
    def _generate_report(self, server_name: str) -> Dict:
        """Generate validation report."""
        
        # Count issues by severity
        errors = [r for r in self.results if r.severity == 'error']
        warnings = [r for r in self.results if r.severity == 'warning']
        info = [r for r in self.results if r.severity == 'info']
        
        # Determine overall status
        if errors:
            status = "NEEDS_FIXES"
        elif warnings:
            status = "MOSTLY_GOOD"
        else:
            status = "EXCELLENT"
        
        print(f"\n{'=' * 70}")
        print("VALIDATION SUMMARY")
        print(f"{'=' * 70}")
        
        print(f"\nServer: {server_name}")
        print(f"Tools Tested: {self.tools_tested}")
        print(f"Status: {status}")
        
        print(f"\nIssues Found:")
        print(f"  🔴 Errors: {len(errors)}")
        print(f"  🟡 Warnings: {len(warnings)}")
        print(f"  🔵 Info: {len(info)}")
        
        if errors:
            print(f"\n❌ Critical Issues ({len(errors)}):")
            for result in errors[:5]:  # Show first 5
                print(f"  • {result.tool_name}: {result.description}")
                print(f"    💡 {result.suggestion}")
        
        if warnings:
            print(f"\n⚠️ Warnings ({len(warnings)}):")
            for result in warnings[:3]:  # Show first 3
                print(f"  • {result.tool_name}: {result.description}")
                print(f"    💡 {result.suggestion}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if not errors and not warnings:
            print("  ✅ Schema validation is excellent!")
        else:
            if errors:
                print("  1. Fix critical validation errors first")
            if warnings:
                print("  2. Add proper input validation for all tools")
            print("  3. Provide clear error messages for validation failures")
            print("  4. Use consistent field naming conventions")
            print("  5. Document all required and optional fields")
        
        print(f"{'=' * 70}")
        
        return {
            "server": server_name,
            "status": status,
            "tools_tested": self.tools_tested,
            "total_issues": len(self.results),
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(info),
            "results": [
                {
                    "issue": r.issue_type.value,
                    "tool": r.tool_name,
                    "description": r.description,
                    "severity": r.severity,
                    "suggestion": r.suggestion
                }
                for r in self.results
            ]
        }


async def main():
    """Run schema validator."""
    import sys
    
    server_name = sys.argv[1] if len(sys.argv) > 1 else "filesystem"
    
    if server_name not in SERVERS:
        print(f"Unknown server: {server_name}")
        print(f"Available servers: {', '.join(SERVERS.keys())}")
        return 1
    
    validator = SchemaValidator()
    report = await validator.validate_schema(server_name)
    
    # Save report
    report_file = f"schema_validation_{server_name}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {report_file}")
    
    # Return non-zero if errors found
    return 1 if report['errors'] > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    import sys
    sys.exit(exit_code)