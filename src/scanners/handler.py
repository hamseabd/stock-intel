"""Scanner Lambda handler — EventBridge triggers with scanner type.

Each EventBridge rule passes {"scanner": "name"} to identify which scan to run.
Scanners check thresholds and queue alerts to SQS for delivery.
"""

import json

from scanners.price_scanner import run_price_scan
from scanners.flow_scanner import run_flow_scan
from scanners.congress_scanner import run_congress_scan
from scanners.darkpool_scanner import run_darkpool_scan
from scanners.risk_scanner import run_risk_scan
from scanners.technicals_scanner import run_technicals_scan
from scanners.earnings_scanner import run_earnings_scan
from scanners.news_scanner import run_news_scan

from shared.log import get_logger, Timer

logger = get_logger(__name__)

SCANNERS = {
    "price": run_price_scan,
    "flow": run_flow_scan,
    "congress": run_congress_scan,
    "darkpool": run_darkpool_scan,
    "risk": run_risk_scan,
    "technicals": run_technicals_scan,
    "earnings": run_earnings_scan,
    "news": run_news_scan,
}


def lambda_handler(event, context):
    """Process an EventBridge scheduled scanner event.

    Args:
        event: {"scanner": "price|flow|congress|darkpool|risk|technicals|earnings|news"}
        context: Lambda context (unused)
    """
    scanner_name = event.get("scanner", "")
    if scanner_name not in SCANNERS:
        logger.error("Unknown scanner type", scanner=scanner_name)
        return {"statusCode": 400}

    with Timer(logger, f"scanner_{scanner_name}"):
        try:
            result = SCANNERS[scanner_name]()
            logger.info("Scanner completed", scanner=scanner_name, **{k: v for k, v in result.items() if isinstance(v, (int, float, str))})
            return {"statusCode": 200, "result": result}
        except Exception as e:
            logger.error("Scanner failed", scanner=scanner_name, exc_info=True)
            return {"statusCode": 500, "error": str(e)}
