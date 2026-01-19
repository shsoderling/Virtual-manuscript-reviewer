"""Command-line interface for Virtual Manuscript Reviewer."""

from pathlib import Path
from typing import Optional

from tap import Tap

from virtual_manuscript_reviewer.manuscript import Manuscript
from virtual_manuscript_reviewer.run_review import run_review, review_manuscript
from virtual_manuscript_reviewer.revision_tracker import RevisionTracker
from virtual_manuscript_reviewer.prompts import BIOMEDICAL_REVIEW_CRITERIA


class ReviewArgs(Tap):
    """Arguments for manuscript review."""

    pdf: str  # Path to the PDF manuscript
    output_dir: str = "reviews"  # Directory to save reviews
    num_rounds: int = 1  # Number of discussion rounds
    review_type: str = "panel"  # Type of review: "panel" or "individual"
    no_pubmed: bool = False  # Disable PubMed search tool
    no_auto_reviewers: bool = False  # Disable auto-generation of specialized reviewers
    no_pdf: bool = False  # Disable PDF generation
    no_mentor: bool = False  # Disable scientific mentor

    # Revision tracking
    project_dir: Optional[str] = None  # Directory for revision tracking project
    author_response: Optional[str] = None  # Path to author response file
    previous_review: Optional[str] = None  # Path to previous review JSON


def main() -> None:
    """Main entry point for the CLI."""
    args = ReviewArgs().parse_args()

    # Load manuscript
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        return

    print(f"Loading manuscript from: {pdf_path}")
    manuscript = Manuscript.from_pdf(pdf_path)
    print(f"Title: {manuscript.title}")
    print(f"Version hash: {manuscript.version_hash}")
    print(f"Pages: {manuscript.metadata.get('page_count', 'unknown')}")
    print()

    # Handle revision tracking if project_dir is specified
    previous_reviews: tuple[str, ...] = ()
    author_response = ""

    if args.project_dir:
        tracker = RevisionTracker(Path(args.project_dir))

        # Load author response if provided
        if args.author_response:
            response_path = Path(args.author_response)
            if response_path.exists():
                with open(response_path, "r") as f:
                    author_response = f.read()
                print(f"Loaded author response from: {response_path}")

        # Add this version to tracker
        version = tracker.add_version(manuscript, author_response=author_response or None)
        print(f"Tracking as version {version.version_number}")

        # Get previous reviews
        previous_reviews = tracker.get_previous_reviews()
        if previous_reviews:
            print(f"Found {len(previous_reviews)} previous review(s)")

    # Load single previous review if specified (without full tracking)
    elif args.previous_review:
        from virtual_manuscript_reviewer.utils import load_review_summary
        review_path = Path(args.previous_review)
        if review_path.exists():
            previous_reviews = (load_review_summary(review_path),)
            print(f"Loaded previous review from: {review_path}")

        if args.author_response:
            response_path = Path(args.author_response)
            if response_path.exists():
                with open(response_path, "r") as f:
                    author_response = f.read()

    # Generate save name
    safe_title = "".join(c if c.isalnum() or c in "- " else "_" for c in manuscript.title[:50])
    save_name = f"{safe_title}_{manuscript.version_hash}"

    print(f"\nStarting {args.review_type} review...")
    print(f"Discussion rounds: {args.num_rounds}")
    print(f"PubMed search: {'disabled' if args.no_pubmed else 'enabled'}")
    print(f"PDF output: {'disabled' if args.no_pdf else 'enabled'}")
    print(f"Scientific mentor: {'disabled' if args.no_mentor else 'enabled'}")
    print()

    # Run review
    summary = run_review(
        manuscript=manuscript,
        review_type=args.review_type,  # type: ignore
        save_dir=Path(args.output_dir),
        save_name=save_name,
        review_criteria=BIOMEDICAL_REVIEW_CRITERIA,
        previous_reviews=previous_reviews,
        author_response=author_response,
        num_rounds=args.num_rounds,
        pubmed_search=not args.no_pubmed,
        return_summary=True,
        auto_generate_reviewers=not args.no_auto_reviewers,
        generate_pdf=not args.no_pdf,
        run_mentor=not args.no_mentor,
    )

    # Update tracker with review
    if args.project_dir and summary:
        tracker = RevisionTracker(Path(args.project_dir))
        version = tracker.get_latest_version()
        if version:
            review_path = Path(args.output_dir) / f"{save_name}.json"
            tracker.add_review(
                version_number=version.version_number,
                review_summary=summary,
                review_path=review_path,
            )
            print(f"\nUpdated revision tracker with review")

            # Generate report
            report_path = tracker.save_report()
            print(f"Saved revision report to: {report_path}")

    print(f"\nReview saved to: {args.output_dir}/{save_name}.md")
    print(f"JSON saved to: {args.output_dir}/{save_name}.json")


if __name__ == "__main__":
    main()
