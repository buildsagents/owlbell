from __future__ import annotations

import argparse
import asyncio
import sys

from backend.leads.agents.company_intelligence import CompanyIntelligenceAgent
from backend.leads.pipeline import run_initial_pipeline, run_followup_pipeline


def parse_cities(raw: str) -> list[dict[str, str]]:
    cities = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            city, state = part.rsplit("-", 1)
            cities.append({"city": city.strip(), "state": state.strip().upper()})
    return cities


async def main() -> None:
    parser = argparse.ArgumentParser(description="Owlbell Lead Generation Pipeline")
    parser.add_argument("--mode", choices=["initial", "followup", "stats", "intel"], default="initial",
                        help="'initial' = scrape+email new leads, 'followup' = send follow-ups, 'stats' = show stats")
    parser.add_argument("--trades", default="plumbing", help="Comma-separated trades; defaults to plumbing only")
    parser.add_argument("--cities", default="Austin-TX,RoundRock-TX,CedarPark-TX", help="Comma-separated City-STATE")
    parser.add_argument("--max-leads", type=int, default=80, help="Max leads to process")
    parser.add_argument("--max-outreach", type=int, default=80, help="Max emails per day")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be sent without sending")
    parser.add_argument("--url", help="Website URL for intel mode")
    parser.add_argument("--name", default="a contractor", help="Business name for intel mode")

    args = parser.parse_args()

    if args.mode == "intel":
        agent = CompanyIntelligenceAgent()
        result = await agent.analyze(args.name, args.url)
        import json
        print(json.dumps(result, indent=2, default=str))
        return

    if args.mode == "stats":
        from backend.leads.outreach import get_stats
        stats = get_stats()
        print(f"Total leads tracked:    {stats.get('total', 0)}")
        print(f"Emails sent:            {stats.get('total_sent', 0)}")
        print(f"Replies received:       {stats.get('total_replied', 0)}")
        print(f"Bounced:                {stats.get('total_bounced', 0)}")
        print(f"Pending follow-ups:     {stats.get('pending_follow_ups', 0)}")
        return

    if args.mode == "followup":
        print("Running follow-up pipeline...")
        result = await run_followup_pipeline(
            max_daily_outreach=args.max_outreach,
            output_file=args.output,
            dry_run=args.dry_run,
        )
        sent = result.get("followups_sent", 0)
        print(f"Follow-ups sent: {sent}")
        if args.dry_run:
            print("(dry run — no emails actually sent)")
        if result.get("status") == "error":
            print(f"ERROR: {result.get('error')}", file=sys.stderr)
            sys.exit(1)
        return

    trades = [t.strip() for t in args.trades.split(",")]
    cities = parse_cities(args.cities)

    print(f"Running lead pipeline: {len(trades)} trades, {len(cities)} cities...")
    if args.dry_run:
        print("(DRY RUN — no emails will be sent)")

    result = await run_initial_pipeline(
        trades=trades,
        cities=cities,
        max_leads=args.max_leads,
        max_daily_outreach=args.max_outreach,
        output_file=args.output,
        dry_run=args.dry_run,
    )

    print(f"Done: {result.get('leads_found', 0)} leads found")
    print(f"      {result.get('with_email', 0)} with email found")
    print(f"      {result.get('emails_sent', 0)} emails sent")
    print(f"      {result.get('elapsed_s', 0)}s elapsed")

    if args.dry_run:
        print("(dry run — no emails actually sent)")

    if result.get("status") == "error":
        print(f"ERROR: {result.get('error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
