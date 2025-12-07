# Extracted Logic Library (The "Crate")

def generate_approval_ui(merchant: str, amount: float, alert_msg: str):
    """Generates generic UI blocks (e.g. for Slack/Teams)."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *Compliance Alert*\n*Merchant:* {merchant}\n*Amount:* ${amount}\n*Alert:* {alert_msg}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "value": "approve"},
                {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, "value": "reject"}
            ]
        }
    ]

def check_business_rules(amount: float, merchant: str):
    """Evaluates transaction against spending limits."""
    SPENDING_LIMIT = 75.00
    
    if amount >= SPENDING_LIMIT:
        return {
            "status": "REVIEW_REQUIRED",
            "ui_blocks": generate_approval_ui(merchant, amount, "Exceeds auto-approval limit")
        }
    
    return {
        "status": "APPROVED",
        "ui_blocks": None
    }