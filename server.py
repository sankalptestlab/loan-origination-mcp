import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from fastmcp import FastMCP
import anthropic
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Loan Origination MCP Server")

def get_db():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@mcp.tool()
def verify_gst(gst_number: str) -> dict:
    """Verify GST number and fetch business report."""
    
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

@mcp.tool()
def verify_pan(pan_number: str) -> dict:
    """Verify PAN number."""
    
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

@mcp.tool()
def parse_gst_report(report: dict) -> dict:
    """Extract structured data from GST report."""
    
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

@mcp.tool()
def calculate_eligibility(business_data: dict) -> dict:
    """Calculate loan eligibility based on business data."""
    
    credit_score = business_data.get("credit_score_numeric", 650)
    annual_turnover = business_data.get("annual_turnover", 0)
    existing_debt = business_data.get("existing_debt", 0)
    requested_amount = business_data.get("requested_amount", 0)
    collateral_available = business_data.get("collateral_available", False)
    filing_compliance = business_data.get("filing_compliance_score", 0.5)
    
    monthly_revenue = annual_turnover / 12
    monthly_obligation = existing_debt / 36
    dti_ratio = monthly_obligation / monthly_revenue if monthly_revenue > 0 else 1.0
    
    if collateral_available:
        max_eligible = min(annual_turnover * 0.5, 50000000)
    else:
        max_eligible = min(annual_turnover * 0.3, 7500000)
    
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

@mcp.tool()
def get_lender_database(filters: Optional[dict] = None) -> List[dict]:
    """Fetch active lenders from database."""
    
    conn = get_db()
    cur = conn.cursor()
    
    query = "SELECT DISTINCT ON (name) * FROM lenders WHERE active = true"
    params = []
    
    if filters:
        if filters.get("min_amount"):
            query += " AND min_amount <= %s"
            params.append(filters["min_amount"])
        if filters.get("max_amount"):
            query += " AND max_amount >= %s"
            params.append(filters["max_amount"])
    
    query += " LIMIT 3"
    
    cur.execute(query, params)
    lenders = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(lender) for lender in lenders]

@mcp.tool()
def extract_intent(message: str) -> dict:
    """Extract intent from customer message using Claude."""
    
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(mcp.get_asgi_app(), host="0.0.0.0", port=port)
```

---

## STEP 4: Update `requirements.txt`

Add `uvicorn`:
```
fastmcp==0.2.0
anthropic==0.40.0
python-dotenv==1.0.0
psycopg2-binary==2.9.9
httpx==0.27.0
pydantic==2.7.0
uvicorn==0.27.0
```

---

## STEP 5: Update `Procfile`
```
web: python server.py