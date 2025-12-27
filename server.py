import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from fastmcp import FastMCP
import anthropic
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

# Initialize FastMCP
mcp = FastMCP("Loan Origination MCP Server")

# Database connection
def get_db():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )

# Anthropic client
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ============================================================
# TOOL 1: verify_gst
# ============================================================
@mcp.tool()
def verify_gst(gst_number: str) -> dict:
    """
    Verify GST number and fetch business report.
    For MVP, returns mock data based on the sample report.
    """
    
    # TODO: Replace with actual API call
    # For now, return mock data from the sample report
    if gst_number == "09AADCF8429L1Z4":
        mock_report = {
            "valid": True,
            "business_name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
            "gst_number": gst_number,
            "constitution": "Private Limited",
            "registration_date": "2021-02-21",
            "address": "C 1,SECTOR 16,Noida,Uttar Pradesh-201301",
            "annual_turnover": 24148440.33,
            "filing_compliance_score": 0.84,
            "credit_score": "CMR-2",
            "active_loans": 19,
            "total_outstanding": 2710443.00,
            "overdue_amount": 138898.00
        }
        
        # Store in verifications table
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO verifications 
            (verification_type, identifier, valid, raw_response, cached, expires_at)
            VALUES (%s, %s, %s, %s, %s, NOW() + INTERVAL '7 days')
            RETURNING id
        """, ("gst", gst_number, True, json.dumps(mock_report), True))
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "valid": True,
            "report": mock_report,
            "cached": False
        }
    else:
        return {
            "valid": False,
            "error": "GST number not found in mock data. For MVP demo, use: 09AADCF8429L1Z4"
        }

# ============================================================
# TOOL 2: verify_pan
# ============================================================
@mcp.tool()
def verify_pan(pan_number: str) -> dict:
    """
    Verify PAN number.
    For MVP, returns mock data.
    """
    
    if pan_number == "AADCF8429L":
        return {
            "valid": True,
            "name": "FINAGG TECHNOLOGIES PRIVATE LIMITED",
            "status": "Active",
            "entity_type": "company"
        }
    else:
        return {
            "valid": False,
            "error": "PAN not found in mock data. For MVP demo, use: AADCF8429L"
        }

# ============================================================
# TOOL 3: parse_gst_report
# ============================================================
@mcp.tool()
def parse_gst_report(report: dict) -> dict:
    """
    Extract structured data from GST report.
    """
    
    # Map credit scores to numeric values
    credit_score_mapping = {
        "CMR-1": 850,
        "CMR-2": 750,
        "CMR-3": 650,
        "CMR-4": 550,
        "CMR-5": 450
    }
    
    parsed = {
        "business_name": report.get("business_name"),
        "constitution": report.get("constitution"),
        "incorporation_date": report.get("registration_date"),
        "annual_turnover": report.get("annual_turnover"),
        "filing_compliance_score": report.get("filing_compliance_score"),
        "credit_score_bureau": report.get("credit_score"),
        "credit_score_numeric": credit_score_mapping.get(report.get("credit_score"), 650),
        "existing_debt": report.get("total_outstanding", 0),
        "overdue_amount": report.get("overdue_amount", 0),
        "active_loan_count": report.get("active_loans", 0)
    }
    
    return parsed

# ============================================================
# TOOL 4: calculate_eligibility
# ============================================================
@mcp.tool()
def calculate_eligibility(business_data: dict) -> dict:
    """
    Calculate loan eligibility based on business data.
    Pure mathematical assessment.
    """
    
    credit_score = business_data.get("credit_score_numeric", 650)
    annual_turnover = business_data.get("annual_turnover", 0)
    existing_debt = business_data.get("existing_debt", 0)
    requested_amount = business_data.get("requested_amount", 0)
    collateral_available = business_data.get("collateral_available", False)
    filing_compliance = business_data.get("filing_compliance_score", 0.5)
    
    # Calculate DTI
    monthly_revenue = annual_turnover / 12
    monthly_obligation = existing_debt / 36  # Assume 3-year average tenure
    dti_ratio = monthly_obligation / monthly_revenue if monthly_revenue > 0 else 1.0
    
    # Determine max eligible amount
    if collateral_available:
        max_eligible = min(annual_turnover * 0.5, 50000000)  # 50% of turnover or 5Cr
    else:
        max_eligible = min(annual_turnover * 0.3, 7500000)   # 30% of turnover or 75L
    
    # Decision logic
    decision = "DECLINED"
    approved_amount = 0
    risk_rating = "HIGH"
    
    if credit_score >= 650 and dti_ratio < 0.5 and filing_compliance >= 0.6:
        if requested_amount <= max_eligible:
            decision = "APPROVED"
            approved_amount = requested_amount
            risk_rating = "LOW" if credit_score >= 750 else "MEDIUM"
        else:
            decision = "CONDITIONAL"
            approved_amount = max_eligible
            risk_rating = "MEDIUM"
    
    return {
        "decision": decision,
        "approved_amount": approved_amount,
        "max_eligible": max_eligible,
        "risk_rating": risk_rating,
        "dti_ratio": round(dti_ratio, 3),
        "credit_score": credit_score,
        "calculations": {
            "monthly_revenue": monthly_revenue,
            "monthly_obligation": monthly_obligation,
            "compliance_score": filing_compliance
        }
    }

# ============================================================
# TOOL 5: get_lender_database
# ============================================================
@mcp.tool()
def get_lender_database(filters: Optional[dict] = None) -> List[dict]:
    """
    Fetch active lenders from database.
    """
    
    conn = get_db()
    cur = conn.cursor()
    
    query = "SELECT * FROM lenders WHERE active = true"
    params = []
    
    if filters:
        if filters.get("min_amount"):
            query += " AND min_amount <= %s"
            params.append(filters["min_amount"])
        if filters.get("max_amount"):
            query += " AND max_amount >= %s"
            params.append(filters["max_amount"])
        if filters.get("min_credit_score"):
            query += " AND min_credit_score <= %s"
            params.append(filters["min_credit_score"])
    
    # Limit to unique lenders only
    query += " GROUP BY name, product_name, interest_rate_min, interest_rate_max, commission_structure, approval_rate_avg"
    query += " LIMIT 3"
    
    cur.execute(query, params)
    lenders = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(lender) for lender in lenders]

# ============================================================
# TOOL 6: calculate_approval_probability
# ============================================================
@mcp.tool()
def calculate_approval_probability(lender_id: int, customer_profile: dict) -> dict:
    """
    Estimate approval probability for a specific lender.
    Phase 1: Simple heuristics.
    """
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lenders WHERE id = %s", (lender_id,))
    lender = cur.fetchone()
    cur.close()
    conn.close()
    
    if not lender:
        return {"error": "Lender not found"}
    
    base_rate = lender["approval_rate_avg"]
    
    # Adjustments
    credit_score = customer_profile.get("credit_score", 650)
    if credit_score >= 750:
        base_rate += 0.10
    elif credit_score >= 700:
        base_rate += 0.05
    
    # Cap at 0.95
    probability = min(base_rate, 0.95)
    
    return {
        "probability": round(probability, 2),
        "confidence": 0.7,
        "factors": {
            "base_rate": lender["approval_rate_avg"],
            "credit_adjustment": probability - lender["approval_rate_avg"]
        }
    }

# ============================================================
# TOOL 7: get_commission_rules
# ============================================================
@mcp.tool()
def get_commission_rules(lender_id: int, loan_amount: float, date: Optional[str] = None) -> dict:
    """
    Calculate commission for a lender.
    """
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lenders WHERE id = %s", (lender_id,))
    lender = cur.fetchone()
    cur.close()
    conn.close()
    
    if not lender:
        return {"error": "Lender not found"}
    
    commission_structure = lender["commission_structure"]
    rate = commission_structure.get("rate", 0)
    
    base_commission = loan_amount * (rate / 100)
    bonus = commission_structure.get("existing_customer_bonus", 0)
    
    return {
        "base_commission": base_commission,
        "campaign_bonus": 0,
        "relationship_bonus": bonus,
        "total_commission": base_commission + bonus,
        "payout_timeline": "On disbursement"
    }

# ============================================================
# TOOL 8: extract_intent
# ============================================================
@mcp.tool()
def extract_intent(message: str, conversation_context: Optional[dict] = None) -> dict:
    """
    Extract intent from customer message using Claude.
    """
    
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Extract structured intent from this message:
            
Message: "{message}"

Return JSON with:
- loan_amount (number or null)
- purpose (string or null)
- urgency (low/medium/high)
- entities (any other relevant info)

Only JSON, no explanation."""
        }]
    )
    
    try:
        intent_data = json.loads(response.content[0].text)
        return {
            "intents": [{"type": "loan_request", "confidence": 0.9, "entities": intent_data}],
            "sentiment": "neutral"
        }
    except:
        return {"intents": [], "sentiment": "neutral", "error": "Could not parse intent"}

# Run server
if __name__ == "__main__":
    mcp.run()
```

### File: `Procfile`
```
web: python server.py
```

### File: `.gitignore`
```
.env
__pycache__/
*.pyc
venv/
.DS_Store