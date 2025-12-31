"""
FastMCP Server for Loan Origination System
Version: Production with Real Claude API
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from fastmcp import FastMCP
from anthropic import Anthropic
from starlette.responses import JSONResponse
from starlette.requests import Request

# Initialize FastMCP server
mcp = FastMCP("Loan Origination MCP Server")

# Initialize Anthropic client
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@mcp.tool()
async def health_check() -> dict:
    """Check server health and dependencies"""
    try:
        conn = get_db_connection()
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "anthropic_key": "configured" if ANTHROPIC_API_KEY else "missing",
        "version": "production-claude-api"
    }

# ============================================================================
# REST API ENDPOINTS WITH REAL CLAUDE
# ============================================================================
async def api_explain_decision(request: Request):
    """REST endpoint for explain_decision"""
    try:
        body = await request.json()
        assessment = body.get("assessment", {})
        recommendation = body.get("recommendation", {})
        
        # Call Claude API for explanation
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Generate a personalized loan approval explanation.

Assessment: {json.dumps(assessment)}
Recommendation: {json.dumps(recommendation)}

Create a friendly, clear explanation covering:
- Approval decision and amount
- Why this lender was recommended
- Next steps

Keep it concise and customer-friendly."""
            }]
        )
        
        return JSONResponse({
            "explanation": response.content[0].text,
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
async def api_extract_intent(request: Request):
    """
    REST endpoint for extract_intent - PRODUCTION VERSION WITH REAL CLAUDE
    Uses Claude Sonnet 4 for intelligent intent extraction
    """
    try:
        body = await request.json()
        message = body.get("message", "")
        
        if not message:
            return JSONResponse({"error": "message field is required"}, status_code=400)
        
        # Call Claude API for intent extraction
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Extract loan intent from this customer message: "{message}"

Analyze the message and return JSON with these fields:
- loan_amount: number in rupees (convert "5 lakhs" to 500000, "2 crores" to 20000000)
- loan_purpose: string (brief description like "vehicle purchase", "business expansion", "inventory", "equipment", "working capital")
- urgency: string (low/medium/high based on words like "urgent", "asap", "planning", "future")
- has_collateral: boolean (true if customer mentions collateral/security/property, false otherwise)

Return ONLY valid JSON with these 4 fields, no other text or markdown.

Examples:
"I need 5 lakhs for a car" -> {{"loan_amount": 500000, "loan_purpose": "vehicle purchase", "urgency": "medium", "has_collateral": false}}
"Urgent! Need 2 crores for expanding to 3 new cities" -> {{"loan_amount": 20000000, "loan_purpose": "business expansion", "urgency": "high", "has_collateral": false}}"""
            }]
        )
        
        # Parse Claude's response
        result_text = response.content[0].text.strip()
        
        # Handle potential markdown code blocks
        if result_text.startswith("```"):
            # Remove markdown code blocks
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON
        try:
            intent = json.loads(result_text)
        except json.JSONDecodeError as e:
            # Fallback: try to extract JSON from text
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                intent = json.loads(json_match.group())
            else:
                raise ValueError(f"Claude response is not valid JSON: {result_text[:200]}")
        
        # Validate required fields
        required_fields = ["loan_amount", "loan_purpose", "urgency", "has_collateral"]
        for field in required_fields:
            if field not in intent:
                return JSONResponse(
                    {"error": f"Missing required field: {field}", "claude_response": result_text}, 
                    status_code=500
                )
        
        return JSONResponse({
            "extracted": True,
            "intent": intent,
            "original_message": message,
            "extracted_at": datetime.now().isoformat(),
            "extraction_method": "claude-api"
        })
        
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"Invalid JSON in request: {str(e)}"}, status_code=400)
    except Exception as e:
        return JSONResponse(
            {"error": f"Server error: {str(e)}", "type": type(e).__name__}, 
            status_code=500
        )

async def api_verify_gst(request: Request):
    """REST endpoint for verify_gst - Mock for MVP"""
    try:
        body = await request.json()
        gst_number = body.get("gst_number", "")
        
        if not gst_number:
            return JSONResponse({"error": "gst_number field is required"}, status_code=400)
        
        # Mock GST data (from FameScore report)
        if gst_number == "09AADCF8429L1Z4":
            result = {
                "gst_number": gst_number,
                "business_name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
                "trade_name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
                "constitution": "Private Limited",
                "address": "C 1,SECTOR 16,Noida,Uttar Pradesh-201301",
                "date_of_registration": "2021-02-21",
                "annual_turnover": 24148440.33,
                "filing_compliance": 0.84,
                "pan_number": "AADCF8429L",
                "credit_score": "CMR-2",
                "existing_loans": 2710443,
                "verified": True,
                "verification_date": datetime.now().isoformat(),
                "verification_method": "mock-api"
            }
        else:
            result = {
                "gst_number": gst_number,
                "verified": False,
                "error": "GST number not found. Use 09AADCF8429L1Z4 for demo.",
                "verification_date": datetime.now().isoformat()
            }
        
        return JSONResponse(result)
        
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_verify_pan(request: Request):
    """REST endpoint for verify_pan - Mock for MVP"""
    try:
        body = await request.json()
        pan_number = body.get("pan_number", "")
        
        if not pan_number:
            return JSONResponse({"error": "pan_number field is required"}, status_code=400)
        
        # Mock PAN data
        if pan_number == "AADCF8429L":
            result = {
                "pan_number": pan_number,
                "name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
                "verified": True,
                "status": "Active",
                "verification_date": datetime.now().isoformat()
            }
        else:
            result = {
                "pan_number": pan_number,
                "verified": False,
                "error": "PAN not found. Use AADCF8429L for demo.",
                "verification_date": datetime.now().isoformat()
            }
        
        return JSONResponse(result)
        
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_parse_gst_report(request: Request):
    """REST endpoint for parse_gst_report"""
    try:
        body = await request.json()
        report = body.get("report", {})
        
        if not report:
            return JSONResponse({"error": "report field is required"}, status_code=400)
        
        # Credit score mapping
        credit_score_map = {
            "CMR-1": 850,
            "CMR-2": 750,
            "CMR-3": 650,
            "CMR-4": 550,
            "CMR-5": 450
        }
        
        result = {
            "business_name": report.get("business_name", ""),
            "gst_number": report.get("gst_number", ""),
            "pan_number": report.get("pan_number", ""),
            "annual_turnover": report.get("annual_turnover", 0),
            "filing_compliance": report.get("filing_compliance", 0),
            "credit_score_text": report.get("credit_score", "CMR-2"),
            "credit_score_numeric": credit_score_map.get(report.get("credit_score", "CMR-2"), 750),
            "existing_debt": report.get("existing_loans", 0),
            "constitution": report.get("constitution", ""),
            "address": report.get("address", ""),
            "parsed_at": datetime.now().isoformat()
        }
        
        return JSONResponse(result)
        
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_calculate_eligibility(request: Request):
    """REST endpoint for calculate_eligibility"""
    try:
        body = await request.json()
        business_data = body.get("business_data", {})
        
        if not business_data:
            return JSONResponse({"error": "business_data field is required"}, status_code=400)
        
        annual_turnover = business_data.get("annual_turnover", 0)
        existing_debt = business_data.get("existing_debt", 0)
        requested_amount = business_data.get("loan_amount", 0)
        credit_score = business_data.get("credit_score_numeric", 750)
        
        # DTI and eligibility calculations
        dti_ratio = existing_debt / annual_turnover if annual_turnover > 0 else 1.0
        max_eligible = annual_turnover * 0.3
        
        # Risk assessment
        if credit_score >= 750:
            risk_rating = "LOW"
            approval_probability = 0.90
        elif credit_score >= 650:
            risk_rating = "LOW-MEDIUM"
            approval_probability = 0.75
        elif credit_score >= 550:
            risk_rating = "MEDIUM"
            approval_probability = 0.60
        else:
            risk_rating = "HIGH"
            approval_probability = 0.30
        
        # Decision logic
        if dti_ratio > 0.4:
            decision = "DECLINED"
            reason = "Debt-to-income ratio too high"
        elif requested_amount > max_eligible:
            decision = "CONDITIONAL"
            reason = f"Requested amount exceeds maximum eligible of ₹{max_eligible:,.0f}"
        elif credit_score < 550:
            decision = "DECLINED"
            reason = "Credit score too low"
        else:
            decision = "APPROVED"
            reason = "All eligibility criteria met"
        
        result = {
            "decision": decision,
            "reason": reason,
            "approved_amount": min(requested_amount, max_eligible) if decision != "DECLINED" else 0,
            "max_eligible": max_eligible,
            "risk_rating": risk_rating,
            "approval_probability": approval_probability,
            "dti_ratio": round(dti_ratio, 3),
            "credit_score": credit_score,
            "assessed_at": datetime.now().isoformat()
        }
        
        return JSONResponse(result)
        
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_get_lenders(request: Request):
    """REST endpoint for get_lender_database"""
    try:
        body = await request.json()
        filters = body.get("filters", None)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT DISTINCT ON (name) 
                id, name, product_name, interest_rate_min, interest_rate_max,
                commission_structure, approval_rate_avg, active
            FROM lenders
            WHERE active = true
        """
        
        params = []
        
        if filters:
            if filters.get("min_amount"):
                query += " AND loan_amount_min <= %s"
                params.append(filters["min_amount"])
            
            if filters.get("credit_score"):
                query += " AND min_credit_score <= %s"
                params.append(filters["credit_score"])
        
        query += " ORDER BY name, id LIMIT 3"
        
        cursor.execute(query, params)
        lenders = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return JSONResponse({"lenders": [dict(l) for l in lenders]})
        
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================================
# MAIN APPLICATION - STARLETTE ROUTE REGISTRATION
# ============================================================================

import sys
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route

async def root_endpoint(request: Request):
    """Root endpoint - service info"""
    return JSONResponse({
        "service": "Loan Origination MCP Server",
        "version": "production-claude-api",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "extract_intent": "/api/extract-intent (POST)",
            "verify_gst": "/api/verify-gst (POST)",
            "verify_pan": "/api/verify-pan (POST)",
            "parse_gst_report": "/api/parse-gst-report (POST)",
            "calculate_eligibility": "/api/calculate-eligibility (POST)",
            "get_lenders": "/api/get-lenders (POST)"
        }
    })

async def health_endpoint(request: Request):
    """Health check endpoint"""
    result = await health_check()
    return JSONResponse(result)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    
    # Check if running in HTTP mode (Render/production) or MCP stdio mode
    if "--http" in sys.argv or os.getenv("RENDER"):
        print(f"Starting HTTP server on port {port}...")
        
        # Register all REST API routes
        routes = [
            Route("/", root_endpoint),
            Route("/health", health_endpoint),
            Route("/api/extract-intent", api_extract_intent, methods=["POST"]),
            Route("/api/verify-gst", api_verify_gst, methods=["POST"]),
            Route("/api/verify-pan", api_verify_pan, methods=["POST"]),
            Route("/api/parse-gst-report", api_parse_gst_report, methods=["POST"]),
            Route("/api/calculate-eligibility", api_calculate_eligibility, methods=["POST"]),
            Route("/api/get-lenders", api_get_lenders, methods=["POST"]),
        ]
        
        # Create Starlette app with routes
        app = Starlette(routes=routes)
        
        # Run with uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        print("Starting MCP server in stdio mode...")
        mcp.run(transport="stdio")
