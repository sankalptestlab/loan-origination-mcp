import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastmcp import FastMCP
from anthropic import Anthropic
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import json
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route, Mount
from starlette.applications import Starlette

# Load environment variables
load_dotenv()

# ============================================================================
# HTTP ENDPOINTS (for browser/health checks)
# ============================================================================

async def root_endpoint(request):
    """Welcome page when accessing via browser"""
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Loan Origination MCP Server</title></head>
    <body style="font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px;">
        <h1>🏦 Loan Origination MCP Server</h1>
        <p><strong>Status:</strong> ✅ Running</p>
        <p><strong>Version:</strong> 1.0.0</p>
        <p><strong>Transport:</strong> SSE (Server-Sent Events)</p>
        
        <h2>Available Tools (7):</h2>
        <ul>
            <li>health_check</li>
            <li>verify_gst</li>
            <li>verify_pan</li>
            <li>parse_gst_report</li>
            <li>calculate_eligibility</li>
            <li>get_lender_database</li>
            <li>extract_intent</li>
        </ul>
        
        <h2>Endpoints:</h2>
        <ul>
            <li><code>GET /</code> - This page</li>
            <li><code>GET /health</code> - Health check (JSON)</li>
            <li><code>POST /sse</code> - MCP protocol endpoint</li>
            <li><code>POST /api/extract-intent</code> - Extract loan intent (REST)</li>
            <li><code>POST /api/verify-gst</code> - Verify GST (REST)</li>
            <li><code>POST /api/verify-pan</code> - Verify PAN (REST)</li>
            <li><code>POST /api/parse-gst-report</code> - Parse GST report (REST)</li>
            <li><code>POST /api/calculate-eligibility</code> - Calculate eligibility (REST)</li>
            <li><code>POST /api/get-lenders</code> - Get lender database (REST)</li>
        </ul>
        
        <p><em>Deployed on Render.com | Connected to Supabase</em></p>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def health_endpoint(request):
    """JSON health check"""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "service": "Loan Origination MCP Server",
        "tools": 7
    })

# ============================================================================
# REST API ENDPOINTS (NEW - ADD THESE)
# ============================================================================

async def api_extract_intent(request):
    """REST endpoint for extract_intent tool"""
    try:
        body = await request.json()
        message = body.get("message", "")
        
        if not message:
            return JSONResponse({"error": "message field is required"}, status_code=400)
        
        result = extract_intent(message)
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_verify_gst(request):
    """REST endpoint for verify_gst tool"""
    try:
        body = await request.json()
        gst_number = body.get("gst_number", "")
        
        if not gst_number:
            return JSONResponse({"error": "gst_number field is required"}, status_code=400)
        
        result = verify_gst(gst_number)
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_verify_pan(request):
    """REST endpoint for verify_pan tool"""
    try:
        body = await request.json()
        pan_number = body.get("pan_number", "")
        
        if not pan_number:
            return JSONResponse({"error": "pan_number field is required"}, status_code=400)
        
        result = verify_pan(pan_number)
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_parse_gst_report(request):
    """REST endpoint for parse_gst_report tool"""
    try:
        body = await request.json()
        report = body.get("report", {})
        
        if not report:
            return JSONResponse({"error": "report field is required"}, status_code=400)
        
        result = parse_gst_report(report)
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_calculate_eligibility(request):
    """REST endpoint for calculate_eligibility tool"""
    try:
        body = await request.json()
        business_data = body.get("business_data", {})
        
        if not business_data:
            return JSONResponse({"error": "business_data field is required"}, status_code=400)
        
        result = calculate_eligibility(business_data)
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_get_lenders(request):
    """REST endpoint for get_lender_database tool"""
    try:
        body = await request.json()
        filters = body.get("filters", None)
        
        result = get_lender_database(filters)
        return JSONResponse({"lenders": result})
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================================
# MCP SERVER INITIALIZATION
# ============================================================================

mcp = FastMCP("Loan Origination MCP Server")
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )

# ============================================================================
# MCP TOOLS (keep all existing tools exactly as they are)
# ============================================================================

@mcp.tool()
def health_check() -> Dict[str, Any]:
    """Check if the MCP server and database are healthy"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "anthropic_key": "configured" if os.getenv("ANTHROPIC_API_KEY") else "missing"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def verify_gst(gst_number: str) -> Dict[str, Any]:
    """Verify GST number and return business data (mock for MVP)"""
    
    if gst_number == "09AADCF8429L1Z4":
        mock_data = {
            "gst_number": gst_number,
            "business_name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
            "trade_name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
            "constitution": "Private Limited",
            "address": "C 1,SECTOR 16,Noida,Uttar Pradesh-201301",
            "date_of_registration": "2021-02-21",
            "annual_turnover": 24148440.33,
            "filing_compliance": 0.84,
            "pan_number": "AADCF8429L",
            "verified": True,
            "verification_date": datetime.now().isoformat()
        }
    else:
        mock_data = {
            "gst_number": gst_number,
            "verified": False,
            "error": "GST number not found in demo database. Use 09AADCF8429L1Z4 for demo.",
            "verification_date": datetime.now().isoformat()
        }
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO verifications (id, verification_type, identifier, raw_response, parsed_data, expires_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                "GST",
                gst_number,
                json.dumps(mock_data),
                json.dumps(mock_data),
                datetime.now() + timedelta(days=7)
            )
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error caching verification: {e}")
    
    return mock_data

@mcp.tool()
def verify_pan(pan_number: str) -> Dict[str, Any]:
    """Verify PAN number (mock for MVP)"""
    
    if pan_number == "AADCF8429L":
        mock_data = {
            "pan_number": pan_number,
            "name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
            "verified": True,
            "status": "Active",
            "verification_date": datetime.now().isoformat()
        }
    else:
        mock_data = {
            "pan_number": pan_number,
            "verified": False,
            "error": "PAN number not found in demo database. Use AADCF8429L for demo.",
            "verification_date": datetime.now().isoformat()
        }
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO verifications (id, verification_type, identifier, raw_response, parsed_data, expires_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                "PAN",
                pan_number,
                json.dumps(mock_data),
                json.dumps(mock_data),
                datetime.now() + timedelta(days=7)
            )
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error caching verification: {e}")
    
    return mock_data

@mcp.tool()
def parse_gst_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Parse GST report and extract structured data"""
    
    credit_score_map = {
        "CMR-1": 850,
        "CMR-2": 750,
        "CMR-3": 650,
        "CMR-4": 550,
        "CMR-5": 450
    }
    
    parsed = {
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
    
    return parsed

@mcp.tool()
def calculate_eligibility(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate loan eligibility based on business data"""
    
    annual_turnover = business_data.get("annual_turnover", 0)
    existing_debt = business_data.get("existing_debt", 0)
    requested_amount = business_data.get("loan_amount", 0)
    credit_score = business_data.get("credit_score_numeric", 750)
    
    dti_ratio = existing_debt / annual_turnover if annual_turnover > 0 else 1.0
    
    max_eligible = annual_turnover * 0.3
    
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
    
    if dti_ratio > 0.4:
        decision = "DECLINED"
        reason = "Debt-to-income ratio too high"
    elif requested_amount > max_eligible:
        decision = "CONDITIONAL"
        reason = f"Requested amount exceeds maximum eligible amount of ₹{max_eligible:,.0f}"
    elif credit_score < 550:
        decision = "DECLINED"
        reason = "Credit score too low"
    else:
        decision = "APPROVED"
        reason = "All eligibility criteria met"
    
    return {
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

@mcp.tool()
def get_lender_database(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Get lenders from database with optional filters"""
    
    try:
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
        
        return [dict(lender) for lender in lenders]
        
    except Exception as e:
        print(f"Error fetching lenders: {e}")
        return []

@mcp.tool()
def extract_intent(message: str) -> Dict[str, Any]:
    """Extract loan intent from customer message using Claude"""
    
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Extract loan intent from this message: "{message}"

Return JSON with:
- loan_amount: number (in rupees, convert lakhs/crores to actual number)
- loan_purpose: string (brief description)
- urgency: string (low/medium/high)
- has_collateral: boolean (if mentioned)

Return ONLY valid JSON, no other text."""
            }]
        )
        
        result_text = response.content[0].text
        result = json.loads(result_text)
        
        return {
            "extracted": True,
            "intent": result,
            "original_message": message,
            "extracted_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "extracted": False,
            "error": str(e),
            "original_message": message,
            "extracted_at": datetime.now().isoformat()
        }

# ============================================================================
# MAIN ENTRY POINT (UPDATED)
# ============================================================================

# ============================================================================
# MAIN ENTRY POINT - HYBRID APPROACH
# ============================================================================

if __name__ == "__main__":
    import sys
    from starlette.applications import Starlette
    from starlette.routing import Route
    import uvicorn
    
    if "--http" in sys.argv or os.getenv("RENDER"):
        port = int(os.getenv("PORT", 10000))
        
        # Create Starlette app with REST API routes
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
        
        app = Starlette(routes=routes)
        
        print(f"Starting REST API server on port {port}...")
        print(f"Endpoints: /api/extract-intent, /api/verify-gst, etc.")
        
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        print("Starting MCP server in STDIO mode...")
        mcp.run(transport="stdio")